# backend-platform

Security-first backend platform in microservices style. See [CHANGELOG.md](CHANGELOG.md) for the recent hardening work.

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

## Browser auth contract
- Browser clients must use the API gateway on the same origin.
- The gateway stores access and refresh tokens in HttpOnly cookies and returns only sanitized auth status JSON to the browser.
- Browser state-changing session calls must send `X-CSRF-Token` with the value from the `bp_csrf_token` cookie.
- Internal services still receive `Authorization: Bearer <access-token>` from the gateway. Do not expose `auth-service` or `user-service` directly outside the private network.
- Accounts are locked after 3 wrong passwords and are unlocked only by a successful password reset.

## Health checks
- Gateway: `GET /v1/health/live`, `GET /v1/health/ready`
- Auth: `GET /v1/health/live`, `GET /v1/health/ready`
- User: `GET /v1/health/live`, `GET /v1/health/ready`
- Notification WIP: `GET /v1/health/live`, `GET /v1/health/ready`

## Tests
- `make test` — unit tests across services + `shared/python`
- `make lint` — ruff across services + `shared/python`
- `make ci`   — `lint` + `test`, the contract the CI mirrors
- `make test-e2e-auth` — gateway auth security e2e (stack must be up)
- `make test-e2e-stack` — full automated docker stack e2e with teardown

## Runbooks
- [Rotate JWT keys](docs/runbooks/rotate-jwt-keys.md) — production zero-downtime key roll
- [Rotate local dev secrets](docs/runbooks/rotate-local-dev-secrets.md) — what to do when a dev `.env` leaks
- [Revoke refresh tokens](docs/runbooks/revoke-refresh-tokens.md) — mass logout procedure
- [Incident response](docs/runbooks/incident-response.md) — triage playbook

## Production Deployment
- Production EC2 deployment uses `Dockerfile` plus `infra/compose/docker-compose.prod.yml`.
- Only `nginx` is exposed publicly; Postgres, Redis, `auth-service`, `user-service`, and the gateway app stay on internal Docker networks.
- Copy `.env.example` to `.env`, set real secrets, and deploy with:
  - `docker compose --env-file .env -f infra/compose/docker-compose.prod.yml up -d --build`
- Auth and session cookies stay `Secure` in production. That means browser login/logout/2FA verification must happen behind HTTPS termination such as an AWS ALB with ACM or a real certificate on Nginx.
- Full AWS EC2 steps are in [docs/deployment/aws-ec2.md](/home/pash666/backend-platform/docs/deployment/aws-ec2.md).
