<div align="center">

<img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/Redis-7+-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
<img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
<img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />

# 🔐 backend-platform

**Production-grade microservices backend platform**  
FastAPI · JWT · TOTP 2FA · PostgreSQL · Redis · Rate Limiting · RBAC

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Services](#-services)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Development](#-development)
- [Security Model](#-security-model)
- [Project Structure](#-project-structure)

---

## 🧭 Overview

`backend-platform` is a **security-first, production-ready microservices backend** built in Python 3.12+. It implements a full authentication and user management system with:

- **JWT access/refresh token rotation** with revocation support
- **TOTP-based 2FA** (Google Authenticator compatible)
- **Role-Based Access Control (RBAC)** with audit events
- **API Gateway** with JWT verification and per-client rate limiting
- **Argon2** password hashing
- **Async-first** architecture throughout

> Designed as a secure, extensible foundation for any product that requires enterprise-grade auth and user management.

---

## 🏗 Architecture

```
                         ┌─────────────────────────────┐
                         │         Client / Browser     │
                         └──────────────┬──────────────┘
                                        │ HTTPS
                         ┌──────────────▼──────────────┐
                         │         API Gateway          │
                         │  :8000  JWT verify + rate    │
                         │         limiting             │
                         └───────┬───────────┬──────────┘
                                 │           │
               ┌─────────────────▼──┐   ┌───▼──────────────────┐
               │    Auth Service    │   │    User Service       │
               │  :8001  JWT, TOTP  │   │  :8002  RBAC, audit   │
               │  refresh rotation  │   │  profiles             │
               └────────┬───────────┘   └────────┬─────────────┘
                        │                        │
               ┌────────▼───────────────────────▼─────────────┐
               │              PostgreSQL (shared)              │
               └───────────────────────────────────────────────┘
                        │
               ┌────────▼──────────┐
               │  Redis             │
               │  token revocation  │
               │  rate limit state  │
               └────────────────────┘
```

---

## 🧩 Services

### `services/auth-service` — Authentication
Handles the full auth lifecycle: registration, login, token issuance, refresh rotation, token revocation, and TOTP 2FA enrollment/verification.

| Responsibility | Details |
|---|---|
| Password hashing | Argon2id |
| Token format | JWT (PyJWT), RS256 or HS256 |
| Refresh token rotation | One-time-use, stored in Redis |
| 2FA | TOTP via `pyotp`, compatible with Google Authenticator |
| Revocation | Token blocklist in Redis |

---

### `services/user-service` — User Management & RBAC
Manages user profiles, roles, permissions, and produces audit events for all significant actions.

| Responsibility | Details |
|---|---|
| Profiles | CRUD, avatar, preferences |
| RBAC | Roles → Permissions model |
| Audit | Immutable event log per user action |

---

### `services/api-gateway` — Edge Gateway
Single entry point for all inbound traffic. Verifies JWT signatures, enforces rate limits, and proxies requests to internal services.

| Responsibility | Details |
|---|---|
| JWT verification | Validates access tokens before proxying |
| Rate limiting | Per-client, backed by Redis |
| Health checks | `/v1/health/live`, `/v1/health/ready` |

---

### `shared/python` — Shared Contracts & Utilities
Internal library with Pydantic schemas, domain contracts, and helpers shared across all services. Published as an editable workspace package.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.12+ |
| **Web framework** | FastAPI (async) |
| **ORM** | SQLAlchemy 2.x (async) |
| **Migrations** | Alembic |
| **Database** | PostgreSQL 15+ |
| **Cache / State** | Redis 7+ |
| **Auth tokens** | PyJWT |
| **Password hashing** | Argon2-cffi |
| **2FA** | pyotp (TOTP / RFC 6238) |
| **Package manager** | uv (workspace) |
| **Linter / Formatter** | Ruff |
| **Type checker** | mypy (strict) |
| **Test runner** | pytest-asyncio |
| **Containerization** | Docker + Docker Compose |

---

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- `make`

### Quickstart (Docker — recommended)

```bash
# 1. Clone the repo
git clone https://github.com/pargevk1996-a11y/backend-platform.git
cd backend-platform

# 2. Install Python dependencies into .venv
make deps

# 3. Bootstrap env files (generates strong secrets automatically)
bash infra/scripts/bootstrap.sh

# 4. Start the full dev stack
make up

# 5. Apply database migrations
make migrate-auth
make migrate-user
```

Services will be available at:

| Service | URL |
|---|---|
| API Gateway | `http://localhost:8000` |
| Auth Service (direct) | `http://localhost:8001` |
| User Service (direct) | `http://localhost:8002` |

### Run services locally (without Docker)

```bash
make run-auth      # http://localhost:8001
make run-user      # http://localhost:8002
make run-gateway   # http://localhost:8000
```

---

## ⚙️ Configuration

Bootstrap generates all secrets automatically:

```bash
bash infra/scripts/bootstrap.sh
```

This creates (or regenerates if insecure values are detected):

```
services/auth-service/.env
services/user-service/.env
services/api-gateway/.env
infra/compose/.env.compose
```

> ⚠️ **Never commit `.env` files.** They are `.gitignore`d by default.  
> The bootstrap script detects legacy insecure DSNs and replaces them automatically.

Key variables set per service:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Async PostgreSQL DSN |
| `REDIS_URL` | Redis connection string with auth |
| `JWT_SECRET` / `JWT_PRIVATE_KEY` | Token signing material |
| `TOTP_ISSUER` | 2FA issuer name shown in authenticator apps |

---

## 📡 API Reference

All services expose interactive OpenAPI docs at `/docs` (Swagger UI) and `/redoc`.

### Health Endpoints (all services)

```
GET /v1/health/live    → 200 OK  (liveness)
GET /v1/health/ready   → 200 OK  (readiness — checks DB + Redis)
```

### Auth Service — Key Endpoints

```
POST /v1/auth/register        Register a new user
POST /v1/auth/login           Login, receive access + refresh tokens
POST /v1/auth/refresh         Rotate refresh token
POST /v1/auth/logout          Revoke current tokens
POST /v1/auth/2fa/enroll      Begin TOTP enrollment, returns QR secret
POST /v1/auth/2fa/verify      Complete TOTP enrollment
POST /v1/auth/2fa/validate    Validate TOTP code on login
```

### User Service — Key Endpoints

```
GET    /v1/users/me           Get current user profile
PATCH  /v1/users/me           Update profile
GET    /v1/users/{id}         Get user by ID (admin / self)
GET    /v1/users/{id}/audit   Fetch audit log for user
```

---

## 🧪 Testing

```bash
# Run all unit tests (all services)
make test

# Per-service unit tests
make test-auth
make test-user
make test-gateway

# End-to-end: gateway auth security flow (stack must be running)
make test-e2e-auth

# Full automated e2e with Docker stack spin-up and teardown
make test-e2e-stack
```

Tests use `pytest-asyncio` in auto mode. All async fixtures use function-scoped event loops by default.

E2E tests are marked with `@pytest.mark.e2e` and are excluded from the default unit test run.

---

## 🧑‍💻 Development

```bash
# Lint each service
make lint-auth
make lint-user
make lint-gateway

# Stop the dev stack
make down

# Full list of available targets
make help
```

### Code Quality Standards

| Tool | Configuration |
|---|---|
| `ruff` | line-length 100, Python 3.12 target, enabled: E, F, I, UP, B, A, S, N, ASYNC, C4, PIE |
| `mypy` | strict mode, `warn_unused_ignores`, `disallow_any_generics` |

---

## 🔒 Security Model

```
┌──────────────────────────────────────────────────┐
│  Access Token (short-lived JWT)                  │
│  → Verified at Gateway, never stored server-side │
├──────────────────────────────────────────────────┤
│  Refresh Token (one-time-use)                    │
│  → Stored in Redis, invalidated on use           │
│  → Rotation: old token revoked, new one issued   │
├──────────────────────────────────────────────────┤
│  TOTP 2FA                                        │
│  → RFC 6238, 30-second window                    │
│  → QR code enrollment compatible with any        │
│    standard authenticator app                    │
├──────────────────────────────────────────────────┤
│  Passwords                                       │
│  → Argon2id, never stored in plaintext           │
├──────────────────────────────────────────────────┤
│  Rate Limiting                                   │
│  → Per-client, enforced at gateway               │
│  → State stored in Redis                         │
└──────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
backend-platform/
├── .github/
│   └── workflows/          # CI/CD pipelines
├── docs/                   # Architecture diagrams, ADRs
├── infra/
│   ├── compose/            # Docker Compose dev stack
│   └── scripts/            # bootstrap.sh, e2e runner
├── services/
│   ├── auth-service/       # FastAPI auth app
│   │   ├── app/
│   │   │   ├── api/        # Route handlers
│   │   │   ├── core/       # Config, security, constants
│   │   │   ├── models/     # SQLAlchemy ORM models
│   │   │   ├── schemas/    # Pydantic request/response models
│   │   │   └── services/   # Business logic
│   │   ├── migrations/     # Alembic migrations
│   │   └── tests/
│   ├── user-service/       # FastAPI user/RBAC app
│   └── api-gateway/        # FastAPI edge gateway
├── shared/
│   └── python/
│       └── src/shared/     # Shared contracts, utilities
├── tests/
│   └── e2e/                # Cross-service e2e test suite
├── conftest.py             # Root pytest config
├── pyproject.toml          # Workspace config, ruff, mypy, pytest
└── Makefile                # All developer commands
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Make your changes, add tests
4. Run linting: `make lint-auth lint-user lint-gateway`
5. Run tests: `make test`
6. Open a Pull Request

Please follow the existing code style — `ruff` and `mypy --strict` must pass with zero errors.

---

## 📄 License

MIT © [pargevk1996-a11y](https://github.com/pargevk1996-a11y)

---

<div align="center">
  <sub>Built with ❤️ using FastAPI, PostgreSQL, Redis, and a security-first mindset.</sub>
</div>
