# Health Connector — AWS Setup Guide

This guide walks a developer through setting up the full Health Connector stack from scratch in a new AWS environment (dev, UAT, or prod).

---

## Architecture Overview

```
Browser
  └── CloudFront (CDN + WAF boundary)
        ├── / (static files)  →  S3 bucket (React SPA)
        └── /api/*            →  API Gateway  →  Lambda (health_connector.py)
                                                      ├── DynamoDB (MOD_Medicaid)
                                                      └── Secrets Manager
```

Key AWS services created by the CDK stack:

| Service | Resource | Purpose |
|---|---|---|
| CloudFront | Distribution | Single origin for UI + API (no CORS issues) |
| S3 | Frontend bucket | Hosts built React app |
| API Gateway | REST API | Routes HTTP requests to Lambda |
| Lambda | `api_handler` | Core business logic |
| DynamoDB | `MOD_Medicaid` | Trip exchange records |
| Secrets Manager | `<secrets_name>` | Via + Lyft + webhook credentials |
| Cognito | User Pool + App Client | Admin UI authentication |

---

## Prerequisites

### Local tools

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.11+ | python.org |
| Node.js | 18+ | nodejs.org |
| AWS CLI | v2 | docs.aws.amazon.com/cli/latest/userguide/install-cliv2 |
| AWS CDK CLI | 2.126.0 | `npm install -g aws-cdk@2.126.0` |
| Git | any | git-scm.com |

Verify:
```bash
python --version
node --version
aws --version
cdk --version
```

### AWS account requirements

- An AWS account with permissions to create: IAM roles, CloudFront, S3, API Gateway, Lambda, DynamoDB, Secrets Manager, Cognito, ACM certificates
- AWS CLI configured with credentials for the target account:
  ```bash
  aws configure          # or use SSO / environment variables
  aws sts get-caller-identity   # verify the right account is active
  ```
- For **prod/UAT with a custom domain**: a registered domain and an ACM certificate in **both** `us-east-1` (required by CloudFront) and the deployment region.

---

## Step 1 — Clone the repository

```bash
git clone <repository-url>
cd MOD-Medicaid
```

---

## Step 2 — Create environment config

The config files are gitignored. Copy the sample for your target environment and fill in your AWS account details:

```bash
# For dev
cp config/dev.sample.py config/dev.py

# For UAT
cp config/uat.sample.py config/uat.py

# For prod
cp config/prod.sample.py config/prod.py
```

Edit the copied file. Required fields:

| Field | Description |
|---|---|
| `aws_account` | Your 12-digit AWS account ID |
| `aws_region` | AWS region to deploy into (e.g. `ap-south-1`) |
| `secrets_name` | Name CDK will use when creating the Secrets Manager secret |
| `version` | Deployment version tag — bump to `v2` to deploy alongside an existing v1 |

Optional fields (can be left blank — fill in via the TMS Settings page after deploy):
- `lyft_client_id`, `lyft_client_secret`, `lyft_program_id`
- `via_client_id`, `via_client_secret`, `via_api_key`

For **prod** with a custom domain, also fill in:
- `domain_name` — your registered domain (e.g. `healthconnector.example.org`)
- `us_east_1_certificate_arn` — ACM cert ARN in `us-east-1`
- `certificate_arn` — ACM cert ARN in the deployment region
- `cognito_domain_prefix` — a globally unique string (e.g. `health-connector-prod-v1`)

---

## Step 3 — Python virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional, for running tests
```

---

## Step 4 — Bootstrap CDK (first time per account/region only)

CDK bootstrap provisions an S3 bucket and IAM roles the toolkit uses to deploy assets:

```bash
cdk bootstrap aws://<YOUR_ACCOUNT_ID>/<YOUR_REGION> -c env=dev
```

This only needs to be done once per account+region combination. If you get "already bootstrapped", skip it.

---

## Step 5 — Deploy the CDK stack

```bash
cdk deploy -c env=dev
```

Replace `dev` with `uat` or `prod` for other environments.

CDK will print a diff and prompt for confirmation before creating resources. Type `y` to proceed.

**Outputs** — after a successful deploy, CDK prints important values. Note these down:

| Output | What it is |
|---|---|
| `CloudFrontURL` | HTTPS URL of the deployed application |
| `ApiGatewayUrl` | API Gateway invoke URL (used in `.env`) |
| `UserPoolId` | Cognito User Pool ID |
| `UserPoolClientId` | Cognito App Client ID |

---

## Step 6 — Populate Secrets Manager

The CDK stack creates the Secrets Manager secret with empty placeholder values. You must fill in the real credentials before the app will work.

### Option A — AWS Console

1. Open **Secrets Manager** in your deployment region
2. Find the secret named `<secrets_name>` (from your config)
3. Click **Retrieve secret value** → **Edit**
4. Fill in the following fields:

| Key | Source |
|---|---|
| `tms_api_base_url` | Via API base URL (from Via dashboard) |
| `tms_client_id` | Via OAuth Client ID |
| `tms_client_secret` | Via OAuth Client Secret |
| `tms_api_key` | Via API Key |
| `tms_token_url` | Via OAuth token endpoint |
| `tms_service_tag` | Via sub-service tag registered for your agency |
| `via_hmac_key` | Shared secret for Via webhook HMAC — see [via_webhook_setup.md](via_webhook_setup.md) |
| `lyft_client_id` | Lyft TAPI Client ID |
| `lyft_client_secret` | Lyft TAPI Client Secret |
| `lyft_program_id` | Lyft TAPI Program ID |
| `lyft_auth_url` | `https://api.lyft.com/oauth/token` |
| `lyft_api_url` | `https://api.lyft.com/v1/tapi/atms/webhooks` |

Additional TMS fields shown on the TMS Settings page (can also be set there):

| Key | Description |
|---|---|
| `tms_provider` | Display name of the TMS provider (e.g. `Via`) |
| `tms_agency_name` | Your agency name |
| `tms_auto_book` | Auto-booking flag (`true` / `false`) |
| `tms_timezone` | Timezone string (e.g. `America/Chicago`) |
| `tms_rider_lookup` | URL or flag for rider lookup integration |
| `tms_webhook_endpoint` | Endpoint Via should call for webhooks |

### Option B — TMS Settings page

After Step 7 (frontend deployed) and Step 8 (Cognito user created), log in to the app and navigate to **TMS Settings**. Enter your Via credentials there and click **Save**. This writes directly to Secrets Manager.

---

## Step 7 — Build and deploy the frontend

### 7a — Create the frontend environment file

```bash
cp middleware/.env.example middleware/.env
```

Edit `middleware/.env` and fill in the values from the CDK Outputs (Step 5):

```
VITE_GOOGLE_MAPS_API_KEY=<your Google Maps API key>
VITE_API_BASE_URL=<ApiGatewayUrl from CDK outputs>
VITE_USER_POOL_ID=<UserPoolId>
VITE_USER_POOL_CLIENT_ID=<UserPoolClientId>
VITE_AWS_REGION=<your deployment region>
```

### 7b — Install Node dependencies

```bash
cd middleware
npm install
cd ..
```

### 7c — Deploy the frontend

```powershell
.\deploy_frontend.ps1 -Env dev -Version v1
```

This script:
1. Runs `npm run build` inside `middleware/`
2. Syncs `middleware/dist/` to the S3 bucket (`medicaid-dev-middlewarefrontend-v1`)
3. Creates a CloudFront invalidation so the new build is served immediately

The CloudFront URL from Step 5 will serve the updated app within ~30 seconds.

---

## Step 8 — Create the first Cognito admin user

The app requires Cognito authentication. Create at least one user using the AWS CLI:

```bash
# 1. Create the user
aws cognito-idp admin-create-user \
  --user-pool-id <UserPoolId> \
  --username admin@example.com \
  --temporary-password "TempPass123!" \
  --message-action SUPPRESS \
  --region <YOUR_REGION>

# 2. Set a permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <UserPoolId> \
  --username admin@example.com \
  --password "PermanentPass123!" \
  --permanent \
  --region <YOUR_REGION>
```

Log in to the app at the CloudFront URL using these credentials.

---

## Step 9 — Configure the Via webhook

Follow [via_webhook_setup.md](via_webhook_setup.md) to:
1. Generate the HMAC shared secret
2. Share it with Via via their dashboard
3. Store it in Secrets Manager under `via_hmac_key`

Give Via the following webhook URL:
```
https://<CloudFrontURL>/via_webhook
```

---

## Redeploying after code changes

**Lambda / CDK changes only:**
```bash
cdk deploy -c env=dev
```

**Frontend changes only:**
```powershell
.\deploy_frontend.ps1 -Env dev -Version v1
```

**Both:**
Run `cdk deploy` first (to update Lambda), then `deploy_frontend.ps1` (to push the new build).

---

## Deploying a new version alongside an existing one

Bump `version` in your config file (e.g. `'v1'` → `'v2'`). CDK will create a new stack `MedicaidStack-dev-v2` with entirely new resources, leaving `MedicaidStack-dev-v1` running. This is useful for zero-downtime migrations.

To delete the old version:
```bash
cdk destroy MedicaidStack-dev-v1 -c env=dev
```

---

## Tearing down an environment

```bash
cdk destroy -c env=dev
```

> **Note:** The DynamoDB table and Secrets Manager secret may have deletion protection. If `cdk destroy` fails for those resources, delete them manually in the AWS Console first.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Login fails / redirects loop | `middleware/.env` has wrong `VITE_USER_POOL_ID` or `VITE_USER_POOL_CLIENT_ID` | Check CDK Outputs; rebuild and redeploy frontend |
| TMS Settings returns 502 | Lambda can't read Secrets Manager | Ensure the IAM role has `secretsmanager:GetSecretValue` on the secret |
| Trip Ingestion returns 422 | TMS Settings are incomplete | Fill in all required fields in TMS Settings page |
| Trip Ingestion "Failed to fetch" | Using absolute API URL instead of CloudFront URL | Always access the app via the CloudFront URL, not directly via API Gateway |
| Webhook returns "No data available!!!" | HMAC signature mismatch | Verify `via_hmac_key` in Secrets Manager matches what was shared with Via |
| Webhook returns `{"error": "HMAC key not configured"}` | `via_hmac_key` is missing or empty in Secrets Manager | Add the key — see [via_webhook_setup.md](via_webhook_setup.md) |
| CloudFront returns 403 on API paths | CloudFront behavior not configured for that path | Run `cdk deploy` to ensure all behaviors are present |
| `cdk deploy` fails: "secret already exists" | A previous stack left the secret behind | Delete the old secret in Secrets Manager Console, then redeploy |

---

## File reference for new developers

| File | Purpose | Gitignored? |
|---|---|---|
| `config/dev.sample.py` | Template for dev environment config | No (committed) |
| `config/dev.py` | Actual dev config with your account IDs | **Yes** — create from sample |
| `config/prod.sample.py` | Template for prod environment config | No (committed) |
| `config/prod.py` | Actual prod config | **Yes** — create from sample |
| `middleware/.env.example` | Template for frontend environment vars | No (committed) |
| `middleware/.env` | Actual frontend environment vars with real keys | **Yes** — create from example |
| `lambda/credentials.sample.py` | Template for on-prem local dev credentials | No (committed) |
| `lambda/credentials.py` | Actual on-prem credentials (filled in locally) | **Yes** — create from sample |
| `cdk.context.json` | Auto-generated by CDK synth; contains account IDs | **Yes** — auto-regenerated |
