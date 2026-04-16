# auth-service

Production-grade authentication service with:
- FastAPI + SQLAlchemy + PostgreSQL + Redis
- JWT (`PyJWT` only)
- Argon2 password hashing
- TOTP (Google Authenticator) with QR provisioning and backup codes
- Refresh token rotation and revocation
- Brute-force protection and rate limiting
- Persistent account lock after 3 wrong passwords until password reset
- Privacy-safe Redis keys (HMAC fingerprints for anti-abuse keys)
- Context-bound login 2FA challenge flow
- Audit logging
