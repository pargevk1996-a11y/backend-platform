# Auth Flow

## Registration
1. Client calls `POST /v1/auth/register`.
2. `auth-service` validates password policy.
3. Password is hashed with Argon2.
4. User row is created.
5. Access + refresh tokens are issued.
6. Refresh token hash is persisted; plaintext refresh token is never stored.

## Login Without 2FA
1. Client calls `POST /v1/auth/login`.
2. Brute-force lock is checked in Redis.
3. Password hash comparison (Argon2 verify).
4. Access + refresh tokens issued.

## Login With 2FA Enabled
1. Client calls `POST /v1/auth/login`.
2. Password succeeds.
3. Service returns `requires_2fa=true` with `challenge_id`.
4. No access token is issued yet.
5. Client submits `POST /v1/auth/login/2fa` with `challenge_id` + `totp_code` or `backup_code`.
6. On success, tokens are issued and challenge is deleted.

## Refresh Rotation
1. Client calls `POST /v1/tokens/refresh`.
2. JWT checks: `iss`, `aud`, `exp`, `type`, `jti`.
3. Refresh hash is matched to DB.
4. Old refresh is marked rotated/revoked.
5. New refresh + access are issued in same family.
6. Reuse detection revokes full family.
