🚀 Backend Platform

Security-first backend platform built with production-grade architecture, strict security policies, and real-world engineering practices.

<img width="1536" height="1024" alt="0e3377be-6476-4c80-9297-4eb35f0cefd3" src="https://github.com/user-attachments/assets/243c8d48-ef23-4f03-94c9-cebecc9ddc9a" />

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

<img width="1536" height="1024" alt="dc6fc0ef-9cce-4270-a16f-54de62db951e" src="https://github.com/user-attachments/assets/0635dca1-3672-468f-b11d-45edb308b95d" />


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

<img width="1536" height="1024" alt="550b8e16-0421-4666-9958-54c6215faaa9" src="https://github.com/user-attachments/assets/04d56061-6c4b-4491-ba03-980ffbe50b4d" />

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

<img width="1536" height="1024" alt="0aa68561-bfaf-49f0-a7ae-c836199e1e35" src="https://github.com/user-attachments/assets/3c629486-d889-4dcc-a9ea-2c05eff589b3" />


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

<img width="1536" height="1024" alt="b0798e8b-57ef-4709-9a6f-6abc8b585a6c" src="https://github.com/user-attachments/assets/ab71d2e6-fa9d-46d6-98ae-62108bb2bd20" />


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

Login/Register request → Gateway
Gateway stores tokens in HttpOnly cookies
Browser receives only safe JSON response
Protected requests use cookies automatically
CSRF token required for state-changing operations

<img width="1536" height="1024" alt="f4629589-0bb0-493f-9f69-a6ac16836d91" src="https://github.com/user-attachments/assets/fb34b333-8ad8-4867-b483-7f532a1ab307" />

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

<img width="1536" height="1024" alt="d574e81f-9ecf-4a8d-9a33-3264f40946d9" src="https://github.com/user-attachments/assets/d41b496a-a5a6-4150-aad5-e7d280439c73" />

📊 CI / Security
Automated pipelines include:

✔ Code validation
✔ Tests
✔ Security scans (Bandit, Trivy)
✔ Policy checks (no insecure libs)
✔ Docker image scanning

<img width="1536" height="1024" alt="8d0ec14d-06e0-4de5-a9ee-b4e122882e7e" src="https://github.com/user-attachments/assets/559ebbbf-dea6-475a-9d07-d471f68ac312" />


📈 Future Improvements
OpenTelemetry (tracing + metrics)
Event-driven communication
Kubernetes deployment
Notification delivery system
SBOM + image signing
