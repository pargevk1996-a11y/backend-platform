# Auth Service API

Base path: `/v1`

## Security invariants
- JWT implementation uses `PyJWT` only.
- If user has 2FA enabled, access/refresh tokens are not returned by `/auth/login`.
- Login 2FA challenge is short-lived and bound to client context.
- Refresh tokens use rotation, reuse detection, and family revocation.

## Endpoints

### `POST /auth/register`
- Purpose: create account and issue initial token pair.
- Request:
```json
{
  "email": "user@example.com",
  "password": "StrongPassword!123"
}
```
- Response `201`:
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### `POST /auth/login`
- Purpose: primary credential step.
- Request:
```json
{
  "email": "user@example.com",
  "password": "StrongPassword!123"
}
```
- Response when 2FA is disabled:
```json
{
  "requires_2fa": false,
  "tokens": {
    "access_token": "<jwt>",
    "refresh_token": "<jwt>",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```
- Response when 2FA is enabled:
```json
{
  "requires_2fa": true,
  "challenge_id": "<uuid>"
}
```

### `POST /auth/login/2fa`
- Purpose: complete login using `challenge_id` + TOTP or backup code.
- Request:
```json
{
  "challenge_id": "<uuid>",
  "totp_code": "123456"
}
```
or
```json
{
  "challenge_id": "<uuid>",
  "backup_code": "ABCD-EFGH"
}
```
- Response:
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### `POST /tokens/refresh`
- Purpose: rotate refresh token and issue new pair.
- Request:
```json
{
  "refresh_token": "<jwt>"
}
```
- Response: token pair payload.

### `POST /tokens/revoke`
- Purpose: revoke one token or full family (logout all sessions).
- Request:
```json
{
  "refresh_token": "<jwt>",
  "revoke_family": true
}
```

### `POST /two-factor/setup`
- Auth required (access token).
- Returns provisioning URI + QR image (`base64`) + secret for manual entry.

### `POST /two-factor/enable`
- Auth required.
- Request:
```json
{
  "totp_code": "123456"
}
```
- Response returns one-time backup codes in plaintext.

### `POST /two-factor/disable`
- Auth required.
- Request requires account password and either TOTP or backup code.

### `POST /two-factor/backup-codes/regenerate`
- Auth required.
- Request requires TOTP or backup code.
- Response returns new plaintext backup codes.

### `GET /health/live`
- Liveness check.

### `GET /health/ready`
- Readiness check (DB + Redis).
