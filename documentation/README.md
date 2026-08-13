# Health Connector — Documentation Index

Health Connector is a Medicaid NEMT broker-to-TMS middleware. It bridges a Lyft TAPI broker and the Via transportation management system: translating trip booking requests, persisting records to DynamoDB, and forwarding real-time status updates back to the broker via Via webhooks.

---

## Quick navigation

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | System overview, component diagram, end-to-end data flows |
| [api.md](api.md) | All API endpoints — method, path, auth, request & response schemas |
| [data-model.md](data-model.md) | DynamoDB table schema, field types, JSON blob patterns |
| [backend.md](backend.md) | Lambda modules, credential chain, secrets_loader key mapping |
| [frontend.md](frontend.md) | Pages, routing, Cognito auth flow, component responsibilities, env vars |
| [deployment.md](deployment.md) | CDK structure, multi-env strategy, versioning, deploy commands |
| [setup.md](setup.md) | Fresh AWS setup from scratch (new developer onboarding) |
| [via_webhook_flow.md](via_webhook_flow.md) | Via webhook architecture, status mapping, HMAC verification |
| [via_webhook_setup.md](via_webhook_setup.md) | Operator guide: generate, store, and verify the HMAC shared key |

---

## Repository layout

```
MOD-Medicaid/
├── app.py                          CDK app entry point
├── config/                         Per-environment CDK config (gitignored — use *.sample.py)
├── health_connector_cdk/           CDK stack definition
├── lambda/                         Lambda function code
│   ├── health_connector.py         API handler entry point
│   ├── secrets_loader.py           Credentials from Secrets Manager
│   └── mod_medicaid/               Business logic modules
├── middleware/                     React frontend (Vite)
│   └── src/
│       ├── auth/                   Cognito auth context + fetch hook
│       ├── components/             Shared UI components
│       └── pages/                  Page components
├── documentation/                  ← you are here
├── deploy_frontend.ps1             Build + S3 sync + CloudFront invalidation
├── requirements.txt                Python CDK dependencies
└── .gitignore
```

---

## Key concepts for new developers

- **Single Lambda, multiple endpoints** — `health_connector.py` handles all routes by switching on `event['requestContext']['resourcePath']`.
- **CloudFront is the single entry point** — all API paths (`/demo_ingestion`, `/tms_settings`, `/dashboard`, `/via_webhook`) are CloudFront behaviors that proxy to API Gateway. The React app never makes cross-origin requests.
- **Credentials live in Secrets Manager** — `secrets_loader.get_credentials()` is the single source of truth for all Via and Lyft credentials. The TMS Settings page in the UI can update them at runtime.
- **`tms_*` → `via_*` key mapping** — Secrets Manager stores keys with `tms_*` prefix (set via the TMS Settings UI). `secrets_loader.py` remaps them to `via_*` names for backward compatibility with internal modules. See [backend.md](backend.md#credential-chain).
- **No CORS** — because all calls go through CloudFront, there are no cross-origin issues. `VITE_API_BASE_URL` in `.env` is a fallback only; in production all API calls use relative URLs.
