# System Design

## Overview
The platform uses a microservices architecture:
- `api-gateway`: public edge, request routing, access-token verification, rate limiting.
- `auth-service`: registration, login, TOTP 2FA, JWT issuance, refresh rotation/revocation.
- `user-service`: user profile domain and RBAC (roles and permissions).
- `shared/python`: shared contracts/utilities.

## Data Stores
- `auth-service`:
  - PostgreSQL: users, refresh token families, sessions, encrypted 2FA secrets, hashed backup codes, audit events.
  - Redis: rate limiting, brute-force counters, login challenge state.
- `user-service`:
  - PostgreSQL: app users, profiles, roles, permissions, role bindings, audit events.
  - Redis: endpoint rate limiting.
- `api-gateway`:
  - Redis: public/protected request throttling.

## Trust Boundaries
- Internet traffic terminates at `api-gateway`.
- Internal service network is isolated (`backend` network in compose prod).
- Only gateway is exposed externally in production.

## Authentication and Authorization
- Access tokens are created in `auth-service` using `PyJWT`.
- `api-gateway` validates access tokens before proxying protected routes.
- `user-service` validates access tokens again for defense in depth.
- RBAC checks are applied in `user-service` endpoints.

## Security Defaults
- Argon2 for password and backup code hashing.
- TOTP secret stored encrypted (Fernet).
- Backup codes stored hashed only.
- Refresh token rotation + family revocation on reuse.
- Centralized exception handlers.
- JSON structured logging.
- Security headers middleware in all services.
