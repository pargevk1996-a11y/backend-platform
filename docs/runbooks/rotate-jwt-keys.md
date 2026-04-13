# Runbook: Rotate JWT Keys

## Preconditions
- Maintenance window approved.
- Access to secure secrets storage.
- Ability to deploy `auth-service`, `user-service`, `api-gateway`.

## Procedure
1. Generate new key pair:
   - `infra/scripts/rotate_keys.sh`
2. Store private/public keys in secrets manager.
3. Update `auth-service` env:
   - `JWT_PRIVATE_KEY`
   - `JWT_PUBLIC_KEY`
4. Deploy `auth-service`.
5. Update and deploy `user-service` + `api-gateway` with new `JWT_PUBLIC_KEY`.
6. Verify:
   - login flow works
   - protected endpoints return 200 with new tokens
   - refresh rotation still works

## Rollback
- Restore previous key set in all services.
- Redeploy in same order.
