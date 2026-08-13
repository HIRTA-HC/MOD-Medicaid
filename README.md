# MOD-Medicaid

<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>

<!-- PROJECT LOGO -->
<br />
<div align="center">

  <h3 align="center">MOD-Medicaid</h3>

  <p align="center">
    Documentation for Health Connector's MOD-Medicaid middleware product can be found in the repository's <a href="https://github.com/HIRTA-HC/MOD-Medicaid/wiki"><strong>Wiki Page»</strong></a>.
    <br />
    <a href="https://github.com/HIRTA-HC/MOD-Medicaid"><strong>Explore the docs »</strong></a>
    <br />
  </p>
</div>

## Quick navigation

| Document | What it covers |
|---|---|
| [architecture.md](documentation/architecture.md) | System overview, component diagram, end-to-end data flows |
| [api.md](documentation/api.md) | All API endpoints — method, path, auth, request & response schemas |
| [data-model.md](documentation/data-model.md) | DynamoDB table schema, field types, JSON blob patterns |
| [backend.md](documentation/backend.md) | Lambda modules, credential chain, secrets_loader key mapping |
| [frontend.md](documentation/frontend.md) | Pages, routing, Cognito auth flow, component responsibilities, env vars |
| [deployment.md](documentation/deployment.md) | CDK structure, multi-env strategy, versioning, deploy commands |
| [setup.md](documentation/setup.md) | Fresh AWS setup from scratch (new developer onboarding) |
| [via_webhook_flow.md](documentation/via_webhook_flow.md) | Via webhook architecture, status mapping, HMAC verification |
| [via_webhook_setup.md](documentation/via_webhook_setup.md) | Operator guide: generate, store, and verify the HMAC shared key |

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
- **`tms_*` → `via_*` key mapping** — Secrets Manager stores keys with `tms_*` prefix (set via the TMS Settings UI). `secrets_loader.py` remaps them to `via_*` names for backward compatibility with internal modules. See [backend.md](documentation/backend.md#credential-chain).
- **No CORS** — because all calls go through CloudFront, there are no cross-origin issues. `VITE_API_BASE_URL` in `.env` is a fallback only; in production all API calls use relative URLs.
