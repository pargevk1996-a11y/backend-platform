# backend-platform

Security-first backend platform in microservices style.

## Services
- `services/auth-service` - authentication, JWT, TOTP 2FA, refresh rotation/revoke
- `services/user-service` - user profiles, RBAC (roles/permissions), audit events
- `services/api-gateway` - edge gateway with JWT verification and rate limiting
- `services/notification-service` - WIP notification service scaffold with health probes
- `shared/python` - versioned shared contracts and utilities

## Tech stack
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- PyJWT
- Argon2
- pyotp

## Quick start
1. Install dependencies:
   - `make deps`
2. Configure env files:
   - `infra/scripts/bootstrap.sh`
   - This generates strong local secrets/keys in:
     - `services/auth-service/.env`
     - `services/user-service/.env`
     - `services/api-gateway/.env`
     - `infra/compose/.env.compose`
   - If legacy insecure DSNs are detected in existing `.env` files, bootstrap regenerates them with secure values.
3. Start infra and services in docker:
   - `make up`
   - Dev compose uses strong DB/Redis passwords from `infra/compose/.env.compose` (including Redis auth).
4. Apply migrations:
   - `make migrate-auth`
   - `make migrate-user`

## Health checks
- Gateway: `GET /v1/health/live`, `GET /v1/health/ready`
- Auth: `GET /v1/health/live`, `GET /v1/health/ready`
- User: `GET /v1/health/live`, `GET /v1/health/ready`
- Notification WIP: `GET /v1/health/live`, `GET /v1/health/ready`

## Tests
- `make test`
- `make test-e2e-auth` (requires running stack)
- `make test-e2e-stack` (full automated docker stack e2e with teardown)
