# API Gateway

Base path: `/v1`

## Role
- Single entrypoint for external clients.
- Routes only whitelisted paths to internal services.
- Enforces rate limits for public and protected traffic.
- Validates access JWT for protected endpoints.
- Sanitizes hop-by-hop headers on request and response.

## Public routes
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/login/2fa`
- `POST /v1/tokens/refresh`
- `POST /v1/tokens/revoke`
- `POST /v1/browser-auth/register`
- `POST /v1/browser-auth/login`
- `POST /v1/browser-auth/login/2fa`
- `POST /v1/browser-auth/refresh`
- `POST /v1/browser-auth/revoke` (sets/clears HttpOnly refresh cookie; JSON omits refresh material)
- `GET /v1/health/live`
- `GET /v1/health/ready`

All other routes are treated as protected and require `Authorization: Bearer <access-token>`.

### Browser BFF (`/v1/browser-auth/*`)

Same upstream behavior as `/v1/auth/*` and `/v1/tokens/*`, but successful token responses **strip** `refresh_token` from JSON and place it in an **HttpOnly** cookie (name `bp_rt` by default, see `REFRESH_COOKIE_*` env vars). Machine clients should continue to call **`/v1/auth/*` and `/v1/tokens/*`** so refresh material stays in the response body.

#### Troubleshooting: `/ui` reload asks for sign-in again

- The demo keeps the access JWT in memory only; reload uses **`POST /v1/browser-auth/refresh`** with the HttpOnly cookie.
- **`Secure` on the refresh cookie** is chosen per request: **on** for HTTPS (or **`X-Forwarded-Proto: https`** from **`TRUSTED_PROXY_IPS`**), **off** for plain HTTP to the gateway — so HTTP and HTTPS can both work without toggling env. Set **`REFRESH_COOKIE_SECURE=true|false`** only to force behavior.
- If TLS terminates at a proxy, ensure **`TRUSTED_PROXY_IPS`** includes that proxy. The gateway only uses **`X-Forwarded-Proto: https`** when **`X-Forwarded-For`** is also present (real proxies send both), so plain HTTP to Docker is not mis-detected as HTTPS.
- The **Gateway URL** field must match the page **origin** (scheme + host + port); otherwise the demo disables the same-origin cookie flow.

## Health endpoints

### `GET /v1/health/live`
- Process liveness.

### `GET /v1/health/ready`
- Checks Redis and upstream services (`auth-service`, `user-service`).

## Proxy contract
- Methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
- Preserves query parameters and body.
- Forwards status code and sanitized response headers.
