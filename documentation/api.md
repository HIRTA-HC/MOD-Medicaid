# API Reference

All endpoints are served through CloudFront. In production, use the CloudFront URL as the base — never call API Gateway directly (it will fail due to CORS and missing CloudFront headers).

Base URL: `https://<cloudfront-domain>`

---

## Authentication

### Cognito-protected endpoints

Send the Cognito `idToken` as a Bearer token:

```
Authorization: Bearer <idToken>
```

The `useAuthFetch` hook in the frontend handles this automatically and will attempt a token refresh on a `401` response before redirecting to the login page.

### HMAC-protected endpoints

`/via_webhook` is authenticated by a per-request HMAC-SHA256 signature. See [via_webhook_setup.md](via_webhook_setup.md).

---

## Active Endpoints

### POST `/demo_ingestion`

Ingests a trip request from the Lyft TAPI broker. Validates TMS credentials, transforms the payload to Via format, books the trip, persists the record to DynamoDB, and returns a 3-stage response.

**Auth:** Cognito JWT

**Request body** (Lyft TAPI trip format):

```json
{
  "atms_ride_id": "string",
  "trip_source_name": {
    "broker_trip_id": "string",
    "tapi_trip_id": "string"
  },
  "scheduled_pickup_time": 1700000000,
  "origin": {
    "address": {
      "address_line1": "string",
      "city": "string",
      "state": "string",
      "zip": "string"
    },
    "lat": 41.8781,
    "lng": -87.6298
  },
  "destination": {
    "address": {
      "address_line1": "string",
      "city": "string",
      "state": "string",
      "zip": "string"
    },
    "lat": 41.9000,
    "lng": -87.6500
  },
  "rider": {
    "first_name": "string",
    "last_name": "string",
    "phone": "string"
  }
}
```

**Response — success (200):**

```json
{
  "broker_request": { "...original Lyft TAPI payload..." },
  "via_payload":    { "...transformed Via trips/request body..." },
  "response":       { "...Via booking confirmation mapped back to Lyft TAPI format..." }
}
```

**Response — incomplete TMS settings (422):**

```json
{
  "error": "TMS settings are incomplete. Please configure the following fields in TMS Settings: API Base URL, Client ID"
}
```

**Response — server error (500):**

```json
{ "error": "string" }
```

---

### GET `/tms_settings`

Returns all `tms_*` keys from the Secrets Manager secret.

**Auth:** Cognito JWT

**Response (200):**

```json
{
  "tms_provider":         "string",
  "tms_agency_name":      "string",
  "tms_api_base_url":     "string",
  "tms_service_tag":      "string",
  "tms_client_id":        "string",
  "tms_client_secret":    "string",
  "tms_api_key":          "string",
  "tms_token_url":        "string",
  "tms_auto_book":        "string",
  "tms_timezone":         "string",
  "tms_rider_lookup":     "string",
  "tms_webhook_endpoint": "string"
}
```

> `tms_client_secret` and `tms_api_key` are included as-is — the frontend masks sensitive fields in the UI.

---

### POST `/tms_settings`

Merges the provided `tms_*` keys into the Secrets Manager secret, then clears the Lambda's in-memory credential cache so the next request picks up the new values.

**Auth:** Cognito JWT

**Request body:** any subset of `tms_*` keys (non-`tms_*` keys in the payload are silently ignored):

```json
{
  "tms_api_base_url": "https://...",
  "tms_client_id":    "...",
  "tms_client_secret":"...",
  "tms_api_key":      "...",
  "tms_token_url":    "https://...",
  "tms_service_tag":  "..."
}
```

**Response — success (200):**

```json
{ "saved": true }
```

**Response — server error (500):**

```json
{ "error": "string" }
```

---

### GET `/dashboard`

Returns all trip records from DynamoDB and pre-computed summary statistics. The full table scan runs in Lambda; pagination is handled client-side (25 records per page).

**Auth:** Cognito JWT

**Response (200):**

```json
{
  "trips": [
    {
      "broker_trip_id": "string",
      "internal_id":    "string",
      "via_trip_id":    "string",
      "rider":          "First Last",
      "pickup":         "123 Main St, City, ST 00000",
      "destination":    "456 Oak Ave, City, ST 00000",
      "status":         "booked | dispatched | completed | canceled",
      "booked_at":      "2024-01-15 09:30 AM",
      "payload": {
        "lyft": { "...original Lyft TAPI request..." },
        "via":  { "...Via booking response..." }
      }
    }
  ],
  "stats": {
    "trips_today":        0,
    "trips_yesterday":    0,
    "booked_total":       0,
    "booked_this_month":  0,
    "booked_last_month":  0,
    "canceled_total":     0,
    "total_trips":        0
  }
}
```

Trips are sorted latest-first by `request_time`. `booked_at` is formatted in Central time (America/Chicago).

**Response — server error (500):**

```json
{ "error": "string" }
```

---

### POST `/via_webhook`

Receives trip status callbacks from Via. Verifies the HMAC-SHA256 signature, dispatches to the appropriate status handler, and forwards a TAPI event to the Lyft broker.

**Auth:** HMAC signature — no Cognito. Via must be configured with the shared secret stored in Secrets Manager under `via_hmac_key`.

**Required header:**
```
X-Via-Signature: <Base64-encoded HMAC-SHA256 of raw request body>
```

**Request body** (Via webhook payload — key fields):

```json
{
  "trip_id": "string",
  "trip_status": "Confirmed | Assigned | Arrived | Boarded | Finished | Canceled | No_Show | Not_Available | Pending",
  "last_status_change_timestamp": 1700000000,
  "driver_info": {
    "first_name": "string",
    "last_name": "string",
    "phone_number": "string"
  },
  "vehicle_info": {
    "model": "string",
    "color": "string",
    "license_plate": "string",
    "current_location": { "lat": 0.0, "lng": 0.0 }
  },
  "latest_pickup_eta": 1700000060,
  "latest_dropoff_eta": 1700000120,
  "rider_boarding_timestamp": 1700000090,
  "rider_dropoff_timestamp": 1700000150,
  "driver_arrival_timestamp": 1700000080
}
```

**Response — signature verified, known status (200):**

Lyft TAPI event object (passed through from `lyft_send_message`).

**Response — signature mismatch or unknown status (200):**

```
"No data available!!!"
```

**Response — HMAC key not configured (200):**

```json
{ "error": "HMAC key not configured" }
```

---

## Legacy Endpoints (return 404)

These endpoints exist in the routing table for backward compatibility but are not implemented:

| Method | Path |
|---|---|
| ANY | `/v1/tapi/trips` |
| ANY | `/v1/tapi/trips/{trip_id}` |
| ANY | `/v1/tapi/trips/{trip_id}/cancel` |
| ANY | `/v1/tapi/providers` |

---

## Legacy Kiosk Endpoints (on-prem only)

These endpoints were used in the original on-prem deployment via ViaConnection.py. They are still present in the routing table but not exposed through the CDK-managed CloudFront distribution.

| Method | Path | Description |
|---|---|---|
| POST | `/kiosk_request` or `/connector` | Book a trip via ViaConnection |
| GET | `/kiosk_status` or `/connector_status` | Check trip status via ViaConnection |
| GET | `/kiosk_request_detail` | Get trip details by trip_id |
