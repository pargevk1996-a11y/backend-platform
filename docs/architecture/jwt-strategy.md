# JWT Strategy

## Library Policy
- Only `PyJWT` is allowed.
- `python-jose` is prohibited.

## Token Types
- `access`: short TTL, used for API authorization.
- `refresh`: long TTL, used only for rotation endpoint.

## Required Claims
All tokens require at least:
- `sub`
- `jti`
- `iss`
- `aud`
- `exp`
- `type`

Access token additionally includes:
- `sid` (session id)

Refresh token additionally includes:
- `sid`
- `family_id`

## Validation Rules
- Verify algorithm, issuer, audience, expiration.
- Validate token `type` matches endpoint expectation.
- Validate UUID claim format for `sub/jti/sid/family_id`.

## Key Management
- Generate RSA key pair via `infra/scripts/rotate_keys.sh`.
- Rollout order:
  1. Deploy auth-service with new private/public pair.
  2. Deploy user-service and api-gateway with new public key.
- Keep previous keys for bounded overlap if zero-downtime rotation is needed.
