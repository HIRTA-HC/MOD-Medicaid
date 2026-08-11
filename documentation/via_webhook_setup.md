# Via Webhook Setup Guide

## Overview

Via sends a POST to `/via_webhook` every time a trip status changes (driver assigned, rider picked up, trip finished, cancelled, etc.). The Health Connector Lambda receives it, verifies the request's authenticity with an HMAC-SHA256 signature, and forwards the status update to the Lyft TAPI broker.

Authentication on this endpoint uses HMAC — not Cognito — because Via's servers cannot carry a Cognito token. Every request Via sends includes an `X-Via-Signature` header containing a Base64-encoded HMAC-SHA256 digest of the raw request body. The Lambda recomputes the digest using the shared secret and rejects the request if the values differ.

---

## Step 1 — Generate the shared secret

Run this once in any Python shell:

```python
import secrets
print(secrets.token_urlsafe(32))
```

Example output: `mK9wR2vXpL4nQ7tJ0sE5cB8yF1dA6hU3zNpQ`

This produces a 43-character URL-safe Base64 string. Copy it — this is your `VIA_HMAC_KEY`. Keep it private; treat it like a password.

> Via's documentation example uses a 30-character alphanumeric string. A 43-character URL-safe Base64 string is equally valid and more secure.

---

## Step 2 — Share the key with Via

Log in to the Via Operations Dashboard and navigate to the webhook configuration section. Paste your `VIA_HMAC_KEY` into the **Webhook shared secret** (or equivalent) field. Via will use this value to sign every outbound webhook POST.

Via uses:
- Hash function: **SHA-256**
- Encoding: **Base64**
- Header: **`X-Via-Signature`**

---

## Step 3 — Store the key in AWS Secrets Manager

The key must be added to the existing Health Connector secret (the same secret that holds `tms_*` and `lyft_*` credentials).

### Option A — AWS Console

1. Open **AWS Secrets Manager** in the correct region
2. Find the secret named `healthconnector-*` (or whatever `SECRETS_NAME` is set to in your environment)
3. Click **Retrieve secret value** → **Edit**
4. Add a new key: `via_hmac_key` with the value you generated in Step 1
5. Click **Save**

### Option B — AWS CLI

```bash
# 1. Fetch the current secret JSON
aws secretsmanager get-secret-value \
  --secret-id <SECRETS_NAME> \
  --query SecretString \
  --output text > secret.json

# 2. Open secret.json in a text editor and add:
#    "via_hmac_key": "your-generated-key-here"

# 3. Push the updated JSON back
aws secretsmanager put-secret-value \
  --secret-id <SECRETS_NAME> \
  --secret-string file://secret.json

# Clean up the local file afterwards — it contains all credentials
rm secret.json
```

> **Do not commit `secret.json` to source control.** Delete it immediately after the `put-secret-value` call.

---

## Step 4 — CDK placeholder (prevents deploy from wiping the key)

The CDK stack seeds the secret with initial values on first deploy. Without a `via_hmac_key` entry, a redeploy would not wipe the key (CDK uses `secret_object_value` which only sets initial values, not updates). However, adding the empty placeholder documents the field and makes it visible in `cdk diff`:

In [health_connector_cdk/health_connector_cdk_stack.py](../health_connector_cdk/health_connector_cdk_stack.py), inside `create_secrets()` → `secret_object_value`, add after `tms_webhook_endpoint`:

```python
'via_hmac_key': SecretValue.unsafe_plain_text(''),
```

This placeholder is intentionally empty — the real value lives only in Secrets Manager, not in CDK source.

---

## Step 5 — Deploy

```bash
cdk deploy -c env=dev
```

The Lambda will pick up the new `via_hmac_key` from Secrets Manager on its next cold start (or after the `_cached` value expires when `_sl._cached = None` is called, e.g., after a TMS Settings save).

---

## Step 6 — Verify the integration

### Send a test POST with a valid signature

```python
import hmac, hashlib, base64, requests, json

SECRET = "your-generated-key-here"
ENDPOINT = "https://<your-cloudfront-domain>/via_webhook"

body = json.dumps({
    "trip_id": "test-trip-001",
    "trip_status": "Confirmed",
    "last_status_change_timestamp": 1700000000
})

dig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
sig = base64.b64encode(dig).decode()

resp = requests.post(
    ENDPOINT,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Via-Signature": sig,
    }
)
print(resp.status_code, resp.text)
```

Expected result: `200` with a non-empty JSON body (the Lyft TAPI callback response).

### Test a bad signature

Send the same request with `X-Via-Signature` set to any random string. Expected response body: `"No data available!!!"` — the Lambda rejected the request before calling Lyft.

### Test missing key

Before storing `via_hmac_key` in Secrets Manager (or with the key temporarily removed), send a valid-looking request. Expected response body: `{"error": "HMAC key not configured"}`.

### CloudWatch logs

In the AWS Console → CloudWatch → Log groups → `/aws/lambda/<function-name>`, filter for the request timestamp. A successful webhook execution logs:
- The decoded HMAC digest
- `via_sig <received-signature>`
- The `trip_status` value being dispatched

---

## Relevant files

| File | Role |
|---|---|
| [lambda/health_connector.py](../lambda/health_connector.py) | Entry point — routes `/via_webhook` POST to `via_interpreter` |
| [lambda/mod_medicaid/webhooks.py](../lambda/mod_medicaid/webhooks.py) | HMAC verify, status dispatch, Lyft callback |
| [lambda/secrets_loader.py](../lambda/secrets_loader.py) | Loads `via_hmac_key` from Secrets Manager |
| [health_connector_cdk/health_connector_cdk_stack.py](../health_connector_cdk/health_connector_cdk_stack.py) | CDK — `create_secrets()` placeholder |
