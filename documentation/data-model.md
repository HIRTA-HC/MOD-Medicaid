# Data Model

## DynamoDB Table: `MOD_Medicaid`

Single table storing all trip exchange records. The table name is controlled by the environment variable `TABLE_NAME` on the Lambda function.

### Key schema

| Attribute | Type | Role |
|---|---|---|
| `atms_ride_id` | String | **Partition key (PK)** — the broker's unique ride identifier, sourced from the Lyft TAPI request |

No sort key. No GSI. Access patterns:
- **Write** at booking time (PutItem by `atms_ride_id`)
- **Full scan** for the Dashboard (`dd_scan_all_trips`)
- **Scan with filter** to look up a record by `via_trip_id` (used by webhook handler `query_ids`)

> For large tables (tens of thousands of records), add a GSI on `request_time` with a fixed partition key (e.g. `ALL`) to enable sorted queries without a full scan.

---

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `atms_ride_id` | String | Broker ride ID (PK). Sourced from `lyft_request_payload.atms_ride_id` |
| `tapi_trip_id` | String | Lyft TAPI trip ID. Sourced from `lyft_request_payload.trip_source_name.tapi_trip_id` |
| `via_trip_id` | String | Via trip ID returned from the `/trips/book` response |
| `request_time` | String | UTC datetime when the booking was ingested. ISO 8601 format: `2024-01-15T14:30:00` |
| `lyft_request_payload` | String | **JSON string** — the full original Lyft TAPI booking request body |
| `via_response_payload` | String | **JSON string** — the full Via booking response (or latest Via webhook payload) |

---

### JSON blob pattern

`lyft_request_payload` and `via_response_payload` are stored as **serialized JSON strings**, not as DynamoDB Maps. This means the full object is a single String attribute. When reading these fields:

```python
import json
lyft = json.loads(item.get('lyft_request_payload') or '{}')
via  = json.loads(item.get('via_response_payload')  or '{}')
```

The `or '{}'` guard handles records where the field is missing or empty.

This pattern was chosen to allow flexible schema evolution (new fields from Via or Lyft don't require DynamoDB schema changes) at the cost of not being able to query inside the blobs.

---

### Example record

```json
{
  "atms_ride_id":    "RIDE-20240115-001",
  "tapi_trip_id":    "tapi-abc123",
  "via_trip_id":     "via-xyz789",
  "request_time":    "2024-01-15T14:30:00",
  "lyft_request_payload": "{\"atms_ride_id\":\"RIDE-20240115-001\",\"trip_source_name\":{\"broker_trip_id\":\"BRK-001\",\"tapi_trip_id\":\"tapi-abc123\"},\"origin\":{\"address\":{\"address_line1\":\"123 Main St\",\"city\":\"Des Moines\",\"state\":\"IA\",\"zip\":\"50309\"},\"lat\":41.59,\"lng\":-93.62},\"destination\":{\"address\":{\"address_line1\":\"456 Oak Ave\",\"city\":\"Des Moines\",\"state\":\"IA\",\"zip\":\"50310\"},\"lat\":41.60,\"lng\":-93.63},\"rider\":{\"first_name\":\"Jane\",\"last_name\":\"Doe\",\"phone\":\"5155550100\"},\"scheduled_pickup_time\":1705327800}",
  "via_response_payload": "{\"trip_id\":\"via-xyz789\",\"trip_status\":\"Confirmed\",\"pre_trip_id\":\"pre-123\"}"
}
```

---

### Field sources

**At booking time** (`dd_new_trip` in `AWS_Data_Operations.py`):

```python
table.put_item(Item={
    'atms_ride_id':          via_response.get('atms_ride_id'),
    'tapi_trip_id':          via_response.get('tapi_trip_id'),
    'via_trip_id':           via_response.get('via_trip_id'),
    'request_time':          datetime.utcnow().isoformat(),
    'lyft_request_payload':  json.dumps(original_lyft_request),
    'via_response_payload':  json.dumps(via_booking_response),
})
```

**At webhook time** (`query_ids` in `webhooks.py`): the record is read by scanning on `via_trip_id`, then `lyft_request_payload` is parsed to recover the broker IDs needed for the TAPI callback.

---

## Secrets Manager Secret

All credentials are stored in a single Secrets Manager secret named by the `secrets_name` field in the environment config.

### Schema

```json
{
  "tms_provider":         "",
  "tms_agency_name":      "",
  "tms_api_base_url":     "",
  "tms_service_tag":      "",
  "tms_client_id":        "",
  "tms_client_secret":    "",
  "tms_api_key":          "",
  "tms_token_url":        "",
  "tms_auto_book":        "",
  "tms_timezone":         "",
  "tms_rider_lookup":     "",
  "tms_webhook_endpoint": "",
  "via_hmac_key":         "",
  "lyft_client_id":       "",
  "lyft_client_secret":   "",
  "lyft_program_id":      "",
  "lyft_auth_url":        "",
  "lyft_api_url":         ""
}
```

### Key mapping (`secrets_loader.py`)

`secrets_loader.get_credentials()` reads the secret and remaps `tms_*` keys to `via_*` names for backward compatibility with internal modules:

| Secrets Manager key | Exposed as |
|---|---|
| `tms_api_base_url` | `via_api_url` |
| `tms_client_id` | `via_client_id` |
| `tms_client_secret` | `via_client_secret` |
| `tms_api_key` | `via_api_key` |
| `tms_token_url` | `via_auth_url` |
| `tms_service_tag` | `tms_service_tag` |
| `via_hmac_key` | `via_hmac_key` |
| `lyft_*` | `lyft_*` (unchanged) |

The cache is a module-level `_cached` dict, reset to `None` after a TMS Settings save so the next Lambda invocation fetches fresh values.
