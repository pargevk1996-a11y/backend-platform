# Runbook: Revoke Refresh Tokens

## Use Cases
- Suspected refresh token leakage.
- Account takeover investigation.

## Procedure
1. Identify affected user/session/family.
2. Call `POST /v1/tokens/revoke` with:
   - `refresh_token`
   - `revoke_family=true`
3. Confirm corresponding rows in `refresh_tokens` are marked revoked.
4. Confirm related `user_sessions` are revoked.
5. Force user re-authentication.

## Broad Revocation (Emergency)
- Temporarily shorten refresh TTL.
- Revoke all active families at DB layer using controlled migration/script.
- Announce forced sign-out.
