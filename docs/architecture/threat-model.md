# Threat Model

## Primary Threats
- Credential stuffing and brute-force login attempts.
- Token theft and replay.
- Refresh token replay after rotation.
- 2FA bypass attempts.
- Sensitive data leakage via logs.
- Unauthorized role escalation.

## Mitigations
- Argon2 password hashing.
- Redis rate limiting + brute-force locks.
- TOTP challenge flow before token issuance.
- Encrypted TOTP secret at rest.
- Backup codes hashed and one-time use.
- JWT claim validation (`iss/aud/exp/type/jti`).
- Refresh family revocation on reuse detection.
- Centralized exception handling and sanitized audit payloads.
- RBAC checks in user-service.
- Gateway route allowlist.

## Residual Risks
- Compromised client devices can leak tokens.
- Operational key rotation mistakes can cause auth outages.
- Misconfigured reverse-proxy IP forwarding can reduce rate-limit accuracy.

## Operational Controls
- Periodic key rotation.
- Audit log monitoring with alerting.
- Incident runbooks for refresh revocation and auth key rollover.
