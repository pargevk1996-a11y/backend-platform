🚀 Backend Platform

Security-first backend platform built with production-grade architecture, strict security policies, and real-world engineering practices.

<img width="1536" height="1024" alt="0e3377be-6476-4c80-9297-4eb35f0cefd3" src="https://github.com/user-attachments/assets/41654de5-4934-4a22-a08f-606d6e9ff56d" />

🧠 Overview

Backend Platform is a microservice-based system designed not just to work — but to be secure, scalable, and production-ready by design.

Instead of building a monolithic API, the system separates responsibilities across services and enforces security and reliability at every layer:

   Token safety (no exposure to browser)
   Cookie-based session handling
   Strong authentication flows (JWT + TOTP 2FA)
   Rate limiting and brute-force protection
   Audit logging and security policies
   CI/CD guardrails and container hardening

This project is not about quantity of endpoints — it's about quality of architecture.

<img width="1536" height="1024" alt="dc6fc0ef-9cce-4270-a16f-54de62db951e" src="https://github.com/user-attachments/assets/1c17db3c-c05e-46a8-8092-0110275d0afa" />

🏗 Architecture

The platform follows a microservice + layered architecture:

         Client → API Gateway → Services → Database
   Core Services
🔐 Auth Service
   Registration / Login
   JWT (access + refresh)
   TOTP 2FA (Google Authenticator)
   Refresh rotation & revoke
   Password reset
   Account lock & audit
👤 User Service
   User profiles
   Roles & permissions (RBAC)
   Authorization context
🌐 API Gateway
   Single entry point
   Cookie-based auth (HttpOnly)
   CSRF protection
   Token orchestration
   Secure routing
🔔 Notification Service (WIP)
   Prepared for async delivery system
📦 Shared Package
   Internal contracts & utilities

<img width="1536" height="1024" alt="550b8e16-0421-4666-9958-54c6215faaa9" src="https://github.com/user-attachments/assets/af875c4b-c1da-4017-94c5-4abf4dfbc018" />

🔐 Security Highlights

This project is built with a security-first mindset:

✅ HttpOnly cookies instead of exposing tokens to browser
✅ CSRF protection for state-changing requests
✅ JWT validation (iss, aud, exp, nbf)
✅ Refresh token rotation with reuse protection
✅ Brute-force detection + persistent account lock
✅ Privacy-safe Redis keys (HMAC-based)
✅ Secure headers (CSP, X-Frame-Options, etc.)
✅ Cache-Control: no-store for sensitive endpoints
❌ No python-jose (blocked by policy)
❌ No weak JWT algorithms in production

<img width="1536" height="1024" alt="0aa68561-bfaf-49f0-a7ae-c836199e1e35" src="https://github.com/user-attachments/assets/9756c764-a993-46e6-aa23-0737f7f7de9d" />

⚙️ Tech Stack

Backend

FastAPI
SQLAlchemy
PostgreSQL
Redis

Security

JWT (RS256)
Argon2 hashing
TOTP (Google Authenticator)

Infrastructure

Docker (multi-stage builds)
Docker Compose (dev + prod)
GitHub Actions (CI + Security + Build)

<img width="1536" height="1024" alt="b0798e8b-57ef-4709-9a6f-6abc8b585a6c" src="https://github.com/user-attachments/assets/524e87eb-ee81-47ce-8561-d48b22ead735" />

📂 Project Structure
services/
  auth-service/
  user-service/
  api-gateway/
  notification-service/

shared/
  python/

infra/
  compose/
  scripts/

Inside each service:

api/           → routes
services/      → business logic
repositories/  → DB access
models/        → ORM models
schemas/       → validation
core/          → config & security

🔄 Auth Flow (Browser)

The browser never sees raw tokens:

   1. Login/Register request → Gateway
   2. Gateway stores tokens in HttpOnly cookies
   3. Browser receives only safe JSON response
   4. Protected requests use cookies automatically
   5. CSRF token required for state-changing operations

<img width="1536" height="1024" alt="f4629589-0bb0-493f-9f69-a6ac16836d91" src="https://github.com/user-attachments/assets/ed19c4c5-bcd6-45d0-b069-624631c131ca" />

🚀 Local Setup
   make deps
   infra/scripts/bootstrap.sh
   make up
   make migrate-auth
   make migrate-user

Open UI:

http://localhost:8000/ui

Health check:

curl http://localhost:8000/v1/health/ready
🧪 Testing
   Unit tests
   Integration tests
   Security tests
   End-to-end (full docker stack)
   make test
   make test-e2e

🐳 Production Features
   Non-root containers
   Read-only filesystem
   Dropped Linux capabilities
   Isolated networks
   Secure environment validation

<img width="1536" height="1024" alt="d574e81f-9ecf-4a8d-9a33-3264f40946d9" src="https://github.com/user-attachments/assets/2c2f5c5a-2705-453a-9a6b-6d5d5e25573f" />

📊 CI / Security

Automated pipelines include:

✔ Code validation
✔ Tests
✔ Security scans (Bandit, Trivy)
✔ Policy checks (no insecure libs)
✔ Docker image scanning

<img width="1536" height="1024" alt="8d0ec14d-06e0-4de5-a9ee-b4e122882e7e" src="https://github.com/user-attachments/assets/1e34e452-2196-49fe-b072-05a0b133d5c2" />

📈 Future Improvements
OpenTelemetry (tracing + metrics)
Event-driven communication
Notification delivery system

[Запись экрана от 2026-04-16 17-01-04.webm](https://github.com/user-attachments/assets/4e8a079b-c2e6-4e0e-8082-f971362e3dcd)
