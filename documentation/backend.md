# Backend

The backend is a single AWS Lambda function written in Python. All HTTP routing is handled by one entry point (`health_connector.py`) that switches on the `resourcePath` from the API Gateway event.

---

## Module Map

```
lambda/
├── health_connector.py          Entry point — routes all API requests
├── secrets_loader.py            Credentials from Secrets Manager (cached)
├── credentials.sample.py        Template for on-prem local dev (gitignored when filled)
├── datastore.py                 SQLite datastore (on-prem only)
├── flask_app.py                 Flask server (on-prem dev only)
└── mod_medicaid/
    ├── mod_medicaid.py          lyft_trip_request() — end-to-end booking orchestration
    ├── lyft_via_xform.py        lyft_to_via() / via_to_lyft() — payload transformation
    ├── via_request.py           Via OAuth2 + trips/request + trips/book
    ├── ViaConnection.py         Legacy kiosk/on-prem Via client
    ├── webhooks.py              via_interpreter() — HMAC verify + status dispatch
    └── AWS_Data_Operations.py   DynamoDB helpers
```

---

## `health_connector.py` — API Entry Point

**Function:** `api_handler(event, context)`

Routes on `event['requestContext']['resourcePath']`:

| Path | Handler |
|---|---|
| `/demo_ingestion` | Validates TMS credentials → `lyft_to_via` → `lyft_trip_request` → `dd_new_trip` |
| `/tms_settings` GET | Reads `tms_*` keys from Secrets Manager |
| `/tms_settings` POST | Merges new `tms_*` keys into Secrets Manager, resets `_cached` |
| `/dashboard` GET | `dd_scan_all_trips` → compute stats → sort → return trips + stats |
| `/via_webhook` POST | `via_interpreter(event)` — HMAC verify + dispatch |
| `/kiosk_*` / `/connector*` | Legacy on-prem routes via `ViaConnection` |
| `/v1/tapi/*` | Returns 404 (legacy stubs) |

All responses share the same structure:

```python
{
    'isBase64Encoded': False,
    'statusCode': status_code,
    'body': json.dumps(output),
    'headers': {
        'content-type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        ...
    }
}
```

---

## `mod_medicaid.py` — Booking Orchestration

**`lyft_trip_request(lyft_payload)`**

End-to-end booking:
1. Transforms payload with `lyft_to_via()`
2. Calls `via_request_trip()` to book through Via
3. Transforms response back with `via_to_lyft()`
4. Returns `(lyft_response, status_code)`

Also defines `cancel_trip()` and `update_trip()` for future use.

---

## `lyft_via_xform.py` — Payload Transformation

**`lyft_to_via(lyft_payload)`**

Maps Lyft TAPI booking request → Via `/trips/request` body:

| Lyft field | Via field | Notes |
|---|---|---|
| `origin.lat/lng` | `pickup.lat/lng` | Direct map |
| `destination.lat/lng` | `dropoff.lat/lng` | Direct map |
| `scheduled_pickup_time` | `pickup_time` | Epoch → ISO UTC string |
| `rider.first_name/last_name/phone` | `passenger_info.name/phone` | Concatenated name |
| *(from Secrets Manager)* | `sub_service_tag` | `tms_service_tag` from `get_credentials()` |

**`via_to_lyft(via_response)`**

Maps Via booking confirmation → Lyft TAPI response format.

---

## `via_request.py` — Via API Client

**`via_request_trip(via_payload)`**

1. Fetches OAuth2 `client_credentials` token from Via token URL
2. `POST /trips/request` → returns `pre_trip_id`
3. `POST /trips/book` with `pre_trip_id` → returns trip confirmation
4. Returns the full booking response

Credentials (`via_client_id`, `via_client_secret`, `via_api_key`, `via_auth_url`, `via_api_url`) come from `secrets_loader.get_credentials()`.

---

## `webhooks.py` — Via Webhook Handler

**`via_interpreter(event)`**

1. Parses `incoming_payload = json.loads(event['body'])`
2. Fetches `via_hmac_key` from `get_credentials()`; returns error dict if blank
3. Generates a random fallback string to force-fail if no `X-Via-Signature` header is present
4. Computes `hmac.digest(raw_body, key, sha256)` and Base64-encodes
5. `hmac.compare_digest(expected, received)` — if mismatch, returns `"No data available!!!"`
6. Dispatches on `trip_status` to the appropriate handler function

**Status handler functions:**

| Function | Via status | Lyft TAPI status | Extra fields |
|---|---|---|---|
| `scheduled()` | `Confirmed` | `scheduled` | `recorded_at` |
| `dispatched()` | `Assigned` | `dispatched` | `eta_pickup`, `location`, `driver`, `vehicle` |
| `arrived()` | `Arrived` | `arrived` | `location`, `driver`, `vehicle` |
| `picked_up()` | `Boarded` | `picked_up` | `eta_dropoff`, `location`, `driver`, `vehicle` |
| `dropped_off()` | `Finished` | `dropped_off` | `actual_miles`, `location`, `driver`, `vehicle` |
| `canceled()` | `Canceled` / `No_Show` / `Not_Available` | `canceled` | `canceled_by`, `reason_for_ride_cancellation` |

Each handler calls `query_ids(via_trip_id)` to look up broker IDs from DynamoDB, builds a TAPI event via `create_message()`, and sends it with `lyft_send_message()`.

**`lyft_send_message(payload)`**

OAuth2 `client_credentials` against `lyft_auth_url`, then `POST` to `lyft_api_url` with the TAPI event payload.

**`query_ids(via_trip_id)`**

DynamoDB scan filtered by `via_trip_id`, parses `lyft_request_payload` JSON, returns `{broker_trip_id, tapi_trip_id, atms_ride_id}`.

---

## `AWS_Data_Operations.py` — DynamoDB Helpers

| Function | Description |
|---|---|
| `dd_new_trip(via_response)` | PutItem — stores a new trip record at booking time |
| `dd_scan_all_trips()` | Full paginated scan — used by `/dashboard` handler |
| `dd_retrieve_by_via_trip_id(via_trip_id)` | Scan with filter — used by webhook `query_ids` |

All functions resolve the table name from the `TABLE_NAME` environment variable via the internal `_table()` helper.

---

## `secrets_loader.py` — Credential Cache

**`get_credentials() → dict`**

- Returns `_cached` dict if already populated (once per warm Lambda instance)
- On first call (or after `_cached = None`): reads the Secrets Manager secret, remaps keys, stores result in `_cached`
- On-prem path: imports `credentials.py` directly when `os.environ['Execution'] == 'On_Prem'`

The cache is intentionally cleared after a TMS Settings save:

```python
# In health_connector.py /tms_settings POST handler:
import secrets_loader as _sl
_sl._cached = None
```

---

## Credential Chain

See [architecture.md — Credential Chain](architecture.md#credential-chain) for the full flow from `config/dev.py` through CDK deploy to Secrets Manager to Lambda.

---

## On-Prem / Local Development

`flask_app.py` wraps `api_handler` in a Flask server for local testing. `datastore.py` provides a SQLite-backed alternative to DynamoDB. Set `os.environ['Execution'] = 'On_Prem'` and fill in `lambda/credentials.py` (copy from `credentials.sample.py`) to run without AWS.

---

## Environment Variables (Lambda)

| Variable | Set by | Used by |
|---|---|---|
| `TABLE_NAME` | CDK (Lambda env) | `AWS_Data_Operations._table()` |
| `SECRETS_NAME` | CDK (Lambda env) | `secrets_loader`, `/tms_settings` handler |
| `AWS_REGION` | Lambda runtime | `secrets_loader` Boto3 client |
| `Execution` | Manual (on-prem only) | `secrets_loader` path selection |
