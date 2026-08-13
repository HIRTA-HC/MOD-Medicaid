# Via Webhook Flow

## Overview

The Via webhook is a server-to-server callback. When a trip's status changes inside the Via platform (driver assigned, rider picked up, trip finished, cancelled, etc.), Via POSTs a notification to `/via_webhook`. The Health Connector Lambda receives it, verifies the signature, maps the Via status to the Lyft TAPI format, and forwards the update back to the broker.

---

## End-to-End Flow

```
Via Platform
    │  Trip status changes (Confirmed, Assigned, Boarded, Finished, Canceled…)
    │  POST /via_webhook  { trip_id, trip_status, driver_info, vehicle_info, timestamps… }
    ▼
API Gateway  (no Cognito auth — open endpoint, authenticated via HMAC signature)
    ▼
health_connector.py  →  ep == '/via_webhook'
    │  calls via_interpreter(event)
    ▼
webhooks.py: via_interpreter()
    │  1. Parses raw event body
    │  2. Fetches via_hmac_key from Secrets Manager
    │  3. Verifies HMAC-SHA256 signature from X-Via-Signature header
    │  4. Maps Via status → handler function
    ▼
Status handler function
    │  Builds a TAPI-format event payload
    │  Calls query_ids(via_trip_id)
    │    → DynamoDB scan by via_trip_id
    │    → returns broker_trip_id, tapi_trip_id, atms_ride_id
    ▼
lyft_send_message()
    │  OAuth2 client-credentials against Lyft auth URL
    │  POST status update to Lyft TAPI endpoint
    ▼
Lyft Broker  (receives trip status in TAPI format)
```

---

## Via Status → Handler Mapping

| Via `trip_status` | Handler function | Lyft TAPI status |
|---|---|---|
| `Confirmed` | `scheduled()` | `scheduled` |
| `Assigned` | `dispatched()` | `dispatched` |
| `Arrived` | `arrived()` | `arrived` |
| `Boarded` | `picked_up()` | `picked_up` |
| `Finished` | `dropped_off()` | `dropped_off` |
| `Canceled` | `canceled()` | `canceled` — reason: `dispatcher_rejected` |
| `No_Show` | `canceled()` | `canceled` — reason: `canceled_no_show` |
| `Not_Available` | `canceled()` | `canceled` — reason: `atms_failure` |
| `Pending`, `Pickup_Determined` | *(no-op)* | — |

---

## Payload Fields per Status

Each handler builds a TAPI event via `create_message()` and `query_ids()`:

| Handler | Additional fields sent |
|---|---|
| `scheduled` | ids, recorded_at, status |
| `dispatched` | + eta_pickup, location, driver, vehicle |
| `arrived` | + location, driver, vehicle |
| `picked_up` | + eta_dropoff, location, driver, vehicle |
| `dropped_off` | + actual_miles, location, driver, vehicle |
| `canceled` | + canceled_by, reason_for_ride_cancellation |

**Base fields** (all statuses):
```json
{
  "event_id": "<uuid4>",
  "occurred_at": "<ISO-8601 UTC>",
  "event_type": "tapi_trip.status.updated",
  "event": {
    "broker_trip_id": "...",
    "tapi_trip_id": "...",
    "atms_trip_id": "...",
    "recorded_at": "...",
    "recorded_at_ms": 1234567890.0,
    "status": "dispatched"
  }
}
```

---

## HMAC Signature Verification

Via signs each webhook with HMAC-SHA256 using a shared secret registered in the Via dashboard:

```python
via_hmac_key = get_credentials().get('via_hmac_key', '')
raw_payload  = event['body']                          # raw request body string
via_sig      = event['headers']['X-Via-Signature']    # provided by Via
dig          = hmac.digest(raw_payload.encode(), via_hmac_key.encode(), sha256)
expected_sig = base64.b64encode(dig).decode()
verified     = hmac.compare_digest(expected_sig, via_sig)
```

`via_hmac_key` is stored in Secrets Manager and loaded via `secrets_loader.get_credentials()`.

If the signature does not match, the handler returns `"No data available!!!"` and does not forward to Lyft.

If `via_hmac_key` is not configured, the handler returns `{"error": "HMAC key not configured"}`.

---

## Why No Cognito Auth on This Endpoint

All other user-facing endpoints use Cognito JWT auth. `/via_webhook` is intentionally open at the API Gateway level because Via's servers cannot carry a Cognito token. Instead, authenticity is proven by the HMAC signature on every request.

Defined in `create_via_webhook_endpoint()` in `health_connector_cdk_stack.py`:
```python
via_webhook.add_method(
    'POST',
    apigw_.LambdaIntegration(api_handler, proxy=True)
    # no authorizer=  ← intentional
)
```

---

## DynamoDB Lookup (`query_ids`)

When Via sends a status update it provides its own `trip_id`. The handler needs the original Lyft TAPI IDs to send back to the broker. `query_ids()` in `webhooks.py` handles this:

1. Scans `MOD_Medicaid` table filtered by `via_trip_id`
2. Parses `lyft_request_payload` JSON string
3. Returns `broker_trip_id` (from `trip_source_name.broker_trip_id`), `tapi_trip_id`, `atms_ride_id`

---

## Relevant Files

| File | Role |
|---|---|
| `lambda/health_connector.py` | Entry point — routes `/via_webhook` POST |
| `lambda/mod_medicaid/webhooks.py` | Full webhook logic — HMAC verify, status mapping, Lyft callback |
| `lambda/mod_medicaid/AWS_Data_Operations.py` | `dd_retrieve_by_via_trip_id()` — DynamoDB lookup |
| `lambda/secrets_loader.py` | Credentials for Lyft OAuth + Via HMAC key |
| `health_connector_cdk/health_connector_cdk_stack.py` | `create_via_webhook_endpoint()` — open API Gateway method |

For setup instructions (generating and storing the HMAC key), see [via_webhook_setup.md](via_webhook_setup.md).
