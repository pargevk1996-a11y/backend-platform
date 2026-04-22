# Two-Factor Authentication

## Components
- `pyotp` for TOTP generation/verification.
- QR provisioning URI generation.
- Backup codes as one-time fallback.

## Secret Handling
- TOTP secret is generated server-side.
- Stored only encrypted using Fernet key from environment.
- Never logged.

## Enable Flow
1. `POST /v1/two-factor/setup` returns provisioning URI and QR (base64 PNG).
2. User scans QR in Google Authenticator.
3. `POST /v1/two-factor/enable` with current TOTP code.
4. If code valid, 2FA enabled and backup codes generated.

## Backup Codes
- Generated once in plaintext response.
- Stored only as Argon2 hashes.
- Marked used after successful fallback auth.

## Login Policy
- If 2FA enabled, access token issuance is blocked until challenge verification succeeds.
- `challenge_id` is short-lived and bound to client context fingerprint (IP + user-agent).
- Challenge storage in Redis uses privacy-preserving fingerprints instead of raw client metadata.
