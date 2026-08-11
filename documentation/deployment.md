# Deployment

## Overview

The project uses AWS CDK v2 (Python) to deploy all infrastructure. A single CDK stack (`MedicaidCdkStack`) creates every AWS resource for one environment + version combination. The frontend is built separately and synced to S3 with a PowerShell script.

---

## CDK Stack

**Entry point:** `app.py`

**Stack class:** `MedicaidCdkStack` in `health_connector_cdk/health_connector_cdk_stack.py`

**Stack naming:** `MedicaidStack-{env}-{version}` (e.g. `MedicaidStack-dev-v1`)

**Environment selection:**

```bash
cdk deploy -c env=dev    # uses config/dev.py
cdk deploy -c env=uat    # uses config/uat.py
cdk deploy -c env=prod   # uses config/prod.py
```

Or via environment variable:

```bash
CDK_ENV=prod cdk deploy
```

Falls back to `dev` if neither is specified.

---

## Resource Naming

All CDK-created resource names encode environment and version to allow multiple stacks in the same account:

| Helper | Pattern | Example |
|---|---|---|
| `config.res(name)` | `Middleware_{env}_{name}_{version}` | `Middleware_dev_Lambda_v1` |
| `config.res_lower(name)` | `middleware-{env}-{name}-{version}` | `middleware-dev-frontendbucket-v1` |

This means you can deploy `v2` alongside `v1` without any resource conflicts.

---

## Multi-Environment Strategy

| Environment | Config file | AWS account | Typical region |
|---|---|---|---|
| `dev` | `config/dev.py` | Dev account | `ap-south-1` |
| `uat` | `config/uat.py` | Prod account | `us-west-1` |
| `prod` | `config/prod.py` | Prod account | `us-west-1` |

Config files are gitignored. Copy from `config/*.sample.py` and fill in your account IDs. See [setup.md](setup.md) for first-time setup.

---

## Deploy Commands

### First time (per account + region)

```bash
# Bootstrap CDK toolkit resources
cdk bootstrap aws://<ACCOUNT_ID>/<REGION> -c env=dev
```

Only needed once per account/region combination.

### Full stack deploy

```bash
# Activate Python venv first
.venv\Scripts\activate   # Windows
source .venv/bin/activate # macOS/Linux

cdk deploy -c env=dev
```

CDK prints a diff and prompts for confirmation. After a successful deploy, note the **Outputs** section — it contains the CloudFront URL, API Gateway URL, Cognito User Pool ID, and App Client ID needed to fill in `middleware/.env`.

### Deploy a specific stack by name

```bash
cdk deploy MedicaidStack-dev-v1 -c env=dev
```

### Preview changes without deploying

```bash
cdk diff -c env=dev
```

---

## Frontend Deploy

The frontend is built and deployed separately from CDK. Run this after `cdk deploy` (CDK must have created the S3 bucket and CloudFront distribution first).

```powershell
# From repo root
.\deploy_frontend.ps1 -Env dev -Version v1
```

**What it does:**

1. Runs `npm run build` inside `middleware/` → outputs to `middleware/dist/`
2. `aws s3 sync middleware/dist/ s3://medicaid-{env}-middlewarefrontend-{version}/ --delete --cache-control "no-cache, no-store, must-revalidate"`
3. Looks up the CloudFront distribution by its `Comment` field (`Medicaid_{env}_Frontend_{version}`)
4. Creates a `/*` invalidation so the new build is served immediately (~30 seconds)

**Prerequisites:**
- `middleware/.env` must exist and contain the correct Cognito + API values
- `npm install` must have been run inside `middleware/`
- AWS CLI must be authenticated with permissions to S3 and CloudFront

---

## Deploying a New Version (v1 → v2)

To deploy a new version without taking down the existing one:

1. Bump `version` in `config/dev.py` from `'v1'` to `'v2'`
2. Run `cdk deploy -c env=dev` — creates `MedicaidStack-dev-v2` as a new, separate stack
3. Run `.\deploy_frontend.ps1 -Env dev -Version v2` to deploy the frontend

`v1` remains running until you explicitly destroy it:

```bash
cdk destroy MedicaidStack-dev-v1 -c env=dev
```

> If the DynamoDB table or Secrets Manager secret has deletion protection, delete them manually in the AWS Console first.

---

## CDK Stack Structure

The stack is organized into discrete methods, each responsible for one logical resource group:

```python
class MedicaidCdkStack(Stack):
    def __init__(self, ...):
        frontend_bucket = self.create_frontend_bucket()
        secret          = self.create_secrets()
        table           = self.create_mod_medicaid_table()
        table2          = self.create_mod_medicaid_history_table()
        api_handler     = self.create_api_handler(secret, table)
        api             = self.create_mod_medicaid_endpoints(api_handler)
        self.create_via_webhook_endpoint(api_handler, api)
        self.create_website_hosting(frontend_bucket, api)
```

| Method | Resources |
|---|---|
| `create_frontend_bucket()` | S3 bucket, public-access block |
| `create_secrets()` | Secrets Manager secret with initial values; grants Lambda `GetSecretValue` + `PutSecretValue` |
| `create_mod_medicaid_table()` | DynamoDB `MOD_Medicaid` table (on-demand billing) |
| `create_api_handler()` | Lambda function, IAM role, DynamoDB read/write grants |
| `create_mod_medicaid_endpoints()` | API Gateway REST API, Cognito authorizer, all Cognito-protected routes |
| `create_via_webhook_endpoint()` | `/via_webhook` POST route (no Cognito auth) |
| `create_website_hosting()` | CloudFront distribution, S3 origin with OAC, API behaviors |

---

## CDK Outputs

After a successful `cdk deploy`, these outputs are printed and available in CloudFormation:

| Output | Description |
|---|---|
| `CloudFrontURL` | HTTPS URL of the application |
| `ApiGatewayUrl` | API Gateway invoke URL (goes into `VITE_API_BASE_URL`) |
| `UserPoolId` | Cognito User Pool ID (goes into `VITE_USER_POOL_ID`) |
| `UserPoolClientId` | Cognito App Client ID (goes into `VITE_USER_POOL_CLIENT_ID`) |

---

## Tearing Down

```bash
cdk destroy -c env=dev
```

This deletes all stack resources. The S3 bucket is emptied automatically before deletion. If CloudFormation fails on DynamoDB or Secrets Manager (deletion protection), delete those manually first.

---

## Python Dependencies

**CDK (root):** `requirements.txt`
```
aws-cdk-lib==2.126.0
constructs>=10.0.0,<11.0.0
boto3
```

**Lambda:** `lambda/requirements.txt`
```
requests-oauthlib==1.3.1
sqlalchemy
tzdata
```

`tzdata` is required by `zoneinfo` on Amazon Linux Lambda runtimes for named timezones like `America/Chicago`.

**Dev tools:** `requirements-dev.txt`
```
pytest==6.2.5
```
