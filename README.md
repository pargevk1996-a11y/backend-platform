# Backend Platform

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/PostgreSQL-Database-336791?style=for-the-badge&logo=postgresql" />
  <img src="https://img.shields.io/badge/Redis-Cache-DC382D?style=for-the-badge&logo=redis" />
  <img src="https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker" />
  <img src="https://img.shields.io/badge/Auth-JWT%20%7C%202FA-black?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python" />
</p>

<p align="center">
  Security-first backend platform with production-grade architecture, token lifecycle controls, and hardening guardrails.
</p>

## Overview

`backend-platform` is a microservice-based backend system built to model secure, production-like engineering practices rather than only expose FastAPI endpoints.

The platform is organized around:

- secure authentication and session management
- clean layered architecture across services
- production-minded infrastructure with Docker, CI, security checks, and observability hooks

Core services:

- `auth-service` for registration, login, JWT issuance, refresh rotation, password reset, 2FA, and audit events
- `user-service` for identity context, roles, permissions, and RBAC
- `api-gateway` as the external entry point for auth-aware routing and edge security
- `notification-service` as a WIP service with health endpoints and baseline hardening
- `shared/python` for internal contracts and shared utilities

## Architecture

The project follows a microservice plus layered architecture:

```text
Client -> API Gateway -> Services -> Datastores
```

Typical layers inside each service:

- `api/` for FastAPI routes
- `services/` for business logic
- `repositories/` for persistence access
- `models/` for ORM entities
- `schemas/` for validation
- `core/` for config, middleware, and security helpers
- `integrations/` for Redis, email, TOTP, and other technical adapters

## Security Highlights

This repository is intentionally opinionated about security:

- HttpOnly cookie-based auth flow at the gateway
- CSRF protection for state-changing requests
- JWT validation for `iss`, `aud`, `exp`, `nbf`, `iat`, and token `type`
- refresh token rotation with reuse detection
- Redis-backed access-session revocation markers
- brute-force protection with privacy-safe HMAC Redis keys
- secure response headers and request context middleware
- production config guardrails for JWT keys, CORS, and cookie security
- CI policy checks for unsafe libraries and runtime `assert`
- Docker hardening with multi-stage builds and non-root runtime containers

## Auth Flow

The browser never needs direct access to raw tokens:

1. Client sends auth requests to the gateway.
2. Gateway proxies the request to the appropriate downstream service.
3. Auth service validates credentials and issues tokens.
4. Gateway stores auth state using secure cookies and returns a safe JSON response.
5. Protected requests are validated through gateway and service-level checks.

## Services

### Auth Service

- registration and login
- JWT access and refresh token issuance
- refresh rotation and revoke flow
- optional TOTP-based 2FA
- password reset with anti-enumeration behavior
- audit event recording

### User Service

- user identity context
- profile data
- roles and permissions
- RBAC checks

### API Gateway

- single external entry point
- protected vs public route handling
- JWT verification for protected endpoints
- header sanitization
- rate limiting
- built-in auth UI

### Notification Service

This service is intentionally marked as WIP. It currently provides:

- health endpoints
- basic config and schemas
- security middleware
- tests and Docker packaging

It is not yet a production delivery system for email, SMS, or push workloads.

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Argon2 password hashing
- TOTP 2FA
- Docker and Docker Compose
- GitHub Actions for CI and security workflows

## Local Setup

```bash
make deps
infra/scripts/bootstrap.sh
make up
make migrate-auth
make migrate-user
```

Open the built-in UI:

```text
http://localhost:8000/ui
```

Check health:

```bash
curl http://localhost:8000/v1/health/ready
```

## Testing

```bash
make test
make test-e2e
```

The test suite covers unit, integration, security, and end-to-end flows across the services.

## Production Notes

Production compose includes:

- non-root containers
- read-only filesystems where possible
- dropped Linux capabilities
- internal backend network isolation
- Python-based health checks

Before deployment, validate:

- `SERVICE_ENV=production`
- asymmetric JWT signing setup such as `RS256`
- explicit `CORS_ALLOWED_ORIGINS`
- `COOKIE_SECURE=true`
- non-default secrets, peppers, and datastore passwords

## Project Book

The repository includes a detailed local project book at `docs/project-book.md` that documents architecture, hardening work, and roadmap notes. That file is intended as a local working document and is ignored in Git where configured.

## License

MIT
