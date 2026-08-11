# Frontend

The frontend is a React 19 single-page application built with Vite and deployed to S3 behind CloudFront.

---

## Technology Stack

| Library | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| React Router DOM | v7 | Client-side routing |
| Vite | 8 | Build tool and dev server |
| lucide-react | latest | Icon set |
| oxlint | latest | Linter |

No UI component library — all styles are hand-written CSS with CSS custom properties (variables).

---

## Source Layout

```
middleware/src/
├── main.jsx                     App entry point (React root, Router)
├── App.jsx                      Root component — layout, sidebar, route definitions
├── App.css                      Layout and sidebar styles
├── index.css                    Global design tokens (CSS variables), component styles
├── auth/
│   ├── AuthContext.jsx          Cognito auth state, login, logout, token refresh
│   └── useAuthFetch.js          Authenticated fetch hook with auto-refresh
├── components/
│   ├── ProtectedRoute.jsx       Route guard — redirects to /login if unauthenticated
│   ├── Sidebar.jsx              Navigation sidebar
│   └── CustomDateTimePicker.jsx Date/time input for trip scheduling
└── pages/
    ├── Login.jsx                Cognito login form
    ├── Dashboard.jsx            Live trip table + stat cards
    ├── TripIngestion.jsx        Trip submission form
    ├── TMSSettings.jsx          TMS credential management
    └── BrokerSettings.jsx       Broker connection settings
```

---

## Routing

Defined in `App.jsx`:

| Path | Component | Auth required |
|---|---|---|
| `/login` | `Login` | No |
| `/` | `Dashboard` | Yes |
| `/trip-ingestion` | `TripIngestion` | Yes |
| `/tms-settings` | `TMSSettings` | Yes |
| `/broker-settings` | `BrokerSettings` | Yes |

All protected routes are wrapped in `<ProtectedRoute>`. Unauthenticated users are redirected to `/login`. After login, the user is redirected back to `/`.

---

## Authentication Flow

Authentication is implemented with direct Cognito API calls — no Amplify dependency.

### `AuthContext.jsx`

Provides: `user`, `login()`, `logout()`, `refreshTokens()`, `initialized`

**State shape (`user`):**

```js
{
  email: string,
  idToken: string,      // used as Bearer token for all API calls
  accessToken: string,
  refreshToken: string,
}
```

State is persisted to `sessionStorage` under the key `hc_user`. On app load, `useEffect` rehydrates from `sessionStorage` and sets `initialized = true`. `ProtectedRoute` waits for `initialized` before redirecting — this prevents a flash-redirect to `/login` on page refresh.

**`login(email, password)`**

Calls Cognito `InitiateAuth` with `USER_PASSWORD_AUTH` flow. Returns the token set on success. Handles the `NEW_PASSWORD_REQUIRED` challenge by calling `RespondToAuthChallenge`.

**`logout()`**

Clears `sessionStorage` and sets `user` to `null`. Router redirects to `/login`.

**`refreshTokens()`**

Calls Cognito `InitiateAuth` with `REFRESH_TOKEN_AUTH`. On success, updates `idToken` and `accessToken` in state and `sessionStorage`. On failure (expired or revoked refresh token), calls `logout()`.

---

### `useAuthFetch.js`

A custom hook that wraps `fetch` with automatic Bearer token injection and transparent token refresh on `401`:

```js
const authFetch = useAuthFetch();
const res = await authFetch('/dashboard');
```

Flow:
1. Attaches `Authorization: Bearer <idToken>` to the request
2. If response is `401`: calls `refreshTokens()`
3. If refresh succeeds: retries the original request with the new token
4. If refresh fails: navigates to `/login` and throws `'Session expired.'`

All pages (`Dashboard`, `TripIngestion`, `TMSSettings`) use `useAuthFetch` — no page constructs auth headers manually.

---

## Pages

### `Login.jsx`

Email + password form. Submits to `AuthContext.login()`. Shows inline error on failure. On success, navigates to `/`.

### `Dashboard.jsx`

Fetches `GET /dashboard` on mount. Displays:

- **Stat cards** (3): Trips Today (vs. yesterday delta), Booked All Time (month-over-month %), Cancellations (cancel rate %)
- **Trip table**: broker_trip_id, internal_id, via_trip_id, rider, pickup, destination, status badge, booked_at
- **Client-side pagination**: 25 records per page, Previous/Next buttons, "Showing X–Y of N trips"
- **Search**: filters by rider name, any trip ID, pickup/destination address (case-insensitive)
- **Status filter**: dropdown for All / Completed / Booked / Dispatched / Canceled
- **Details drawer**: slides in on "Details" click, shows trip overview + `lyft` and `via` JSON panels

Status badge colors are driven by CSS classes: `.status-badge-inline.completed`, `.booked`, `.dispatched`, `.canceled`.

`StatTrend` component: positive delta → green ↑, negative → red ↓, zero → gray "No change".

### `TripIngestion.jsx`

Multi-field form for submitting a trip. Fields:
- Rider first/last name, phone
- Pickup address (line1, city, state, zip)
- Destination address
- Scheduled pickup datetime
- atms_ride_id, broker_trip_id, tapi_trip_id

On submit: `POST /demo_ingestion`. Shows a spinner on the button during the request. Displays the 3-stage JSON response (`broker_request`, `via_payload`, `response`) in syntax-highlighted panels. Toast notification on success or error.

### `TMSSettings.jsx`

Form with fields for all `tms_*` keys. On load: `GET /tms_settings`. On save: `POST /tms_settings`. Shows a page spinner during initial load. Shows a toast on save success or failure. Fields show a "not saved" visual indicator when edited but not yet saved.

### `BrokerSettings.jsx`

Broker connection configuration page.

---

## Design System

All design tokens are CSS custom properties defined in `index.css`:

```css
:root {
  --color-primary: #3b82f6;
  --color-danger:  #ef4444;
  --color-success: #22c55e;
  --bg-sidebar:    #1e293b;
  /* ... */
}
```

Dark/light mode follows the system preference via `prefers-color-scheme`. The page renders in the viewer's theme — `body` has an explicit background token so it never inherits the browser's ground.

Key CSS patterns:
- `.page-loader` — centered spinner + message for loading states
- `.toast / .toast-success / .toast-error` — bottom-screen notification strip
- `.status-badge-inline` — colored trip status pills
- `.mono-cell` — monospace, nowrap table cells for IDs
- `.stat-trend.up / .down / .negative` — colored delta indicators on stat cards
- `.json-pre` — syntax-highlighted JSON display (Postman-style coloring)

---

## Environment Variables

Defined in `middleware/.env` (gitignored — copy from `.env.example`):

| Variable | Source | Used for |
|---|---|---|
| `VITE_USER_POOL_ID` | CDK Output | Cognito API calls (`InitiateAuth`, `RefreshToken`) |
| `VITE_USER_POOL_CLIENT_ID` | CDK Output | Cognito App Client identifier |
| `VITE_AWS_REGION` | Your config | Cognito endpoint construction |
| `VITE_GOOGLE_MAPS_API_KEY` | Google Cloud Console | Address autocomplete (if enabled) |
| `VITE_API_BASE_URL` | CDK Output (API Gateway URL) | Fallback only — production calls use relative URLs through CloudFront |

> In production, all API calls use relative URLs (`/demo_ingestion`, `/dashboard`, etc.) that are served through CloudFront. `VITE_API_BASE_URL` is only a fallback reference.

---

## Build and Deploy

```powershell
# Build
cd middleware
npm install
npm run build    # outputs to middleware/dist/

# Deploy (from repo root)
.\deploy_frontend.ps1 -Env dev -Version v1
```

`deploy_frontend.ps1` syncs `middleware/dist/` to S3 and invalidates the CloudFront cache. See [deployment.md](deployment.md) for details.

`middleware/dist/` is gitignored — it is always regenerated from source.
