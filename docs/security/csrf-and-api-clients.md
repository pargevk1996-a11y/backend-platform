# CSRF, Bearer APIs, and browser cookies

## Bearer-only (machine / non-browser API clients)

Protected routes are authenticated with `Authorization: Bearer <access-token>`. Browsers do **not** automatically attach this header to cross-site requests unless application JavaScript supplies it.

That means classic **cross-site request forgery (CSRF)** against state-changing API calls that rely **only** on the `Authorization` header is generally **not applicable**: a malicious site cannot read the token from another origin and cannot set arbitrary `Authorization` headers on credentialed fetches to arbitrary URLs in another origin’s name without a separate flaw (e.g. XSS).

The gateway lists `X-CSRF-Token` in CORS allowed headers for future use; there is **no CSRF middleware** today because session state is not carried in cookies for those clients.

## Browser demo UI and `/v1/browser-auth/*`

The static demo under the gateway may use **HttpOnly** cookies for the **refresh** token (issued by `POST /v1/browser-auth/*` on the gateway). Those endpoints are intended for **same-origin** use only (CORS with credentials is still subject to an explicit origin allowlist in staging/production).

- **Refresh cookie**: `HttpOnly`, `SameSite=Lax`, `Secure` outside `development` (override with `REFRESH_COOKIE_SECURE` if needed).
- **Access token**: short-lived JWT. For the same-origin flow, the demo keeps it **only in JavaScript memory** (`state`), **not** in `localStorage` or `sessionStorage`, so a full page reload relies on **silent refresh** via the HttpOnly cookie (`POST /v1/browser-auth/refresh`). Any **XSS in the page can still steal the access token from memory** while the tab is open — that residual risk requires strict CSP, subresource integrity, and avoidance of `unsafe-inline` scripts (see gateway `SecurityHeadersMiddleware` for `/ui`).
- **Cross-origin Gateway URL**: if the user points “Gateway URL” at another origin, the UI **blocks** account actions and shows a banner — storing refresh/access pairs in `localStorage` for arbitrary API hosts is not supported.

If you later introduce **cookie-based access sessions** (e.g. opaque session id for API auth) or **mutating** routes that rely on **only** cookies without `SameSite=Strict` and a tight CORS policy, add an explicit CSRF policy (double-submit token, synchronizer pattern, or framework-native CSRF) and validate it on mutating methods.

## When to add CSRF checks

Add CSRF validation when **all** of the following apply:

1. Authentication for the request depends on **cookies** sent automatically by the browser, and  
2. The API allows **cross-site** requests that can trigger state changes (e.g. relaxed CORS with `credentials`), or  
3. The session cookie is not sufficiently constrained by `SameSite` for your threat model.

Until then, document Bearer-only behavior (this file) and keep CORS allowlists strict in production.
