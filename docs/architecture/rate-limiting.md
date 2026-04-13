# Rate Limiting

## Scope
- `auth-service`:
  - registration
  - login
  - login/2fa
  - refresh
- `user-service`:
  - profile write
  - role assignment
- `api-gateway`:
  - public auth endpoints
  - protected endpoints

## Storage
- Redis increment + expiry windows.
- Keys include scope + client fingerprint + time bucket.
- Client fingerprint is HMAC-based, so raw IP/email values are not stored in Redis keys.

## Brute Force Protection
`auth-service` also maintains dedicated lock keys for:
- login attempts
- 2FA attempts

After threshold is reached:
- account/IP tuple is locked for configured lock window.
