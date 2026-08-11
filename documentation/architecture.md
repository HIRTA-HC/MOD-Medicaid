# Architecture

## Overview

Health Connector acts as a translation layer between a Lyft TAPI broker and the Via TMS. It has two primary flows:

1. **Inbound booking** — broker sends a trip request → Lambda transforms it → Via books the trip → response returned to broker
2. **Status updates** — Via POSTs webhook events as trip status changes → Lambda maps the status → forwarded to Lyft TAPI

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     AWS Account                          │
│                                                          │
│  Browser / Broker                                        │
│      │                                                   │
│      ▼                                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │              CloudFront Distribution              │   │
│  │  Behavior: /  ──────────────────────► S3 Bucket  │   │
│  │  Behavior: /demo_ingestion ──────┐               │   │
│  │  Behavior: /tms_settings ────────┤               │   │
│  │  Behavior: /dashboard ───────────┤               │   │
│  │  Behavior: /via_webhook ─────────┤               │   │
│  └─────────────────────────────────-┼───────────────┘   │
│                                     │                    │
│                                     ▼                    │
│                          ┌──────────────────┐           │
│                          │   API Gateway    │           │
│                          │  (REST, proxy)   │           │
│                          └────────┬─────────┘           │
│                                   │                      │
│                                   ▼                      │
│                    ┌──────────────────────────┐          │
│                    │   Lambda: api_handler    │          │
│                    │   health_connector.py    │          │
│                    └─────┬────────┬───────────┘          │
│                          │        │                      │
│          ┌───────────────┘        └──────────────┐       │
│          ▼                                       ▼       │
│  ┌───────────────┐                    ┌─────────────────┐│
│  │   DynamoDB    │                    │ Secrets Manager ││
│  │  MOD_Medicaid │                    │  tms_* + lyft_* ││
│  └───────────────┘                    └─────────────────┘│
│                                                          │
│  ┌──────────────────────────────────┐                    │
│  │         Cognito User Pool        │                    │
│  │  (authenticates admin UI users)  │                    │
│  └──────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────┘

External systems:
  Via TMS API   ◄──── Lambda books trips, Via calls /via_webhook
  Lyft TAPI     ◄──── Lambda forwards status updates
```

---

## End-to-End: Trip Booking Flow

```
Browser (Trip Ingestion page)
  │  POST /demo_ingestion  { Lyft TAPI trip request }
  │  Authorization: Bearer <Cognito idToken>
  ▼
CloudFront  →  API Gateway  →  Lambda (health_connector.py)
  │
  ├─ 1. Validate TMS credentials — 6 required keys in Secrets Manager
  │      If any missing → HTTP 422 with list of missing fields
  │
  ├─ 2. lyft_to_via(payload)
  │      Transforms Lyft TAPI format → Via trips/request body
  │      - lat/lng from address fields
  │      - epoch timestamps
  │      - passenger_info from rider object
  │      - sub_service_tag from tms_service_tag in Secrets Manager
  │
  ├─ 3. via_request_trip(via_payload)  [via_request.py]
  │      - OAuth2 client_credentials → Via token endpoint
  │      - POST /trips/request  →  pre_trip_id
  │      - POST /trips/book     →  trip confirmation
  │
  ├─ 4. via_to_lyft(via_response)
  │      Transforms Via booking confirmation → Lyft TAPI response
  │
  ├─ 5. dd_new_trip(via_response)  [AWS_Data_Operations.py]
  │      DynamoDB PutItem:
  │        atms_ride_id (PK), tapi_trip_id, via_trip_id,
  │        lyft_request_payload (JSON string),
  │        via_response_payload (JSON string),
  │        request_time (UTC ISO string)
  │
  └─ 6. Return { broker_request, via_payload, response }
         HTTP 200 (or 500 on error)
```

---

## End-to-End: Via Webhook Flow

```
Via Platform  (trip status changes)
  │  POST /via_webhook  { trip_id, trip_status, driver_info, ... }
  │  X-Via-Signature: <Base64 HMAC-SHA256>
  ▼
CloudFront  →  API Gateway  (no Cognito auth — open endpoint)
  ▼
Lambda (health_connector.py)  →  via_interpreter(event)  [webhooks.py]
  │
  ├─ 1. Retrieve via_hmac_key from Secrets Manager
  ├─ 2. HMAC-SHA256 verify: hmac.digest(raw_body, key, sha256) == X-Via-Signature
  │      Mismatch → return "No data available!!!"
  │
  ├─ 3. Dispatch on trip_status:
  │      Confirmed → scheduled()
  │      Assigned  → dispatched()
  │      Arrived   → arrived()
  │      Boarded   → picked_up()
  │      Finished  → dropped_off()
  │      Canceled / No_Show / Not_Available → canceled()
  │
  ├─ 4. query_ids(via_trip_id)  [webhooks.py]
  │      DynamoDB scan by via_trip_id
  │      Parse lyft_request_payload JSON
  │      Returns: broker_trip_id, tapi_trip_id, atms_ride_id
  │
  └─ 5. lyft_send_message(tapi_event)
         OAuth2 → Lyft auth URL
         POST TAPI event → Lyft TAPI endpoint
```

---

## Credential Chain

```
config/dev.py  (gitignored)
  │  aws_account, aws_region, secrets_name,
  │  initial credential values (usually empty)
  ▼
CDK deploy  →  Secrets Manager secret created
  │
  ▼
TMS Settings page  (or AWS Console)
  │  Writes tms_* + lyft_* keys to Secrets Manager
  ▼
secrets_loader.get_credentials()  (cached per Lambda warm instance)
  │  Reads secret, maps:
  │    tms_api_base_url   → via_api_url
  │    tms_client_id      → via_client_id
  │    tms_client_secret  → via_client_secret
  │    tms_api_key        → via_api_key
  │    tms_token_url      → via_auth_url
  │    tms_service_tag    → tms_service_tag
  │    via_hmac_key       → via_hmac_key
  │    lyft_*             → lyft_* (unchanged)
  ▼
ViaConnection.py / via_request.py / webhooks.py
  (consume via_* and lyft_* keys)
```

---

## CloudFront Behavior Routing

| Path pattern | Origin | Auth |
|---|---|---|
| `/` (default) | S3 bucket (React SPA) | None |
| `/demo_ingestion` | API Gateway | Cognito JWT (Bearer token) |
| `/tms_settings` | API Gateway | Cognito JWT |
| `/dashboard` | API Gateway | Cognito JWT |
| `/via_webhook` | API Gateway | HMAC signature |

All API behaviors use `AllowedMethods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE` with CORS disabled (same origin via CloudFront).

---

## Infrastructure as Code

All AWS resources are defined in a single CDK stack (`MedicaidCdkStack`) in `health_connector_cdk/health_connector_cdk_stack.py`. The stack name encodes environment and version: `MedicaidStack-{env}-{version}`.

Key CDK methods:

| Method | Resources created |
|---|---|
| `create_frontend_bucket()` | S3 bucket, bucket policy |
| `create_secrets()` | Secrets Manager secret, grants Lambda read+write |
| `create_mod_medicaid_table()` | DynamoDB table (`MOD_Medicaid`) |
| `create_api_handler()` | Lambda function, IAM role |
| `create_mod_medicaid_endpoints()` | API Gateway REST API, Cognito authorizer, routes |
| `create_via_webhook_endpoint()` | `/via_webhook` route (no Cognito) |
| `create_website_hosting()` | CloudFront distribution, behaviors, OAC |

See [deployment.md](deployment.md) for deploy commands and multi-environment strategy.
