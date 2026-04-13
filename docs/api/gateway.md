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
- `GET /v1/health/live`
- `GET /v1/health/ready`

All other routes are treated as protected and require `Authorization: Bearer <access-token>`.

## Health endpoints

### `GET /v1/health/live`
- Process liveness.

### `GET /v1/health/ready`
- Checks Redis and upstream services (`auth-service`, `user-service`).

## Proxy contract
- Methods: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
- Preserves query parameters and body.
- Forwards status code and sanitized response headers.
