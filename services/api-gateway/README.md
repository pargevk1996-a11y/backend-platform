# api-gateway

Security-first API gateway:
- request routing to auth/user services (allowlist-based)
- JWT verification with `PyJWT` for protected routes
- browser auth cookies with HttpOnly access/refresh tokens
- CSRF guard for cookie-authenticated state-changing requests
- Redis-backed rate limiting
- privacy-safe HMAC client fingerprints for anti-abuse keys
- centralized exception handling
- health checks with upstream readiness probes
