# Runbook: Rotate Local Development Secrets

Use this runbook when:

- Real credentials ended up in `services/*/.env` or `infra/compose/.env.compose`.
- A contributor leaves the project.
- Any secret is suspected to be compromised (e.g. screen-shared, committed to a
  wrong branch, leaked in a log).

All commands assume `$PWD` is the repository root
`/home/pash666/backend-platform`.

---

## 0. Inventory: what lives where

| Secret                       | File on disk                                 | Also appears in…                  |
| ---------------------------- | -------------------------------------------- | --------------------------------- |
| `AUTH_DB_PASSWORD`           | `infra/compose/.env.compose`                 | `services/auth-service/.env` (in DATABASE_URL) |
| `USER_DB_PASSWORD`           | `infra/compose/.env.compose`                 | `services/user-service/.env` (in DATABASE_URL) |
| `REDIS_PASSWORD`             | `infra/compose/.env.compose`                 | `services/{auth,user,api-gateway}/.env` (in REDIS_URL) |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | `services/auth-service/.env`         | `services/{user-service,api-gateway}/.env` (public key only) |
| `REFRESH_TOKEN_HASH_PEPPER`  | `services/auth-service/.env`                 | —                                 |
| `PRIVACY_KEY_PEPPER`         | `services/{auth,user,api-gateway}/.env`      | Per-service value (each service hashes only its own data) |
| `PASSWORD_RESET_TOKEN_PEPPER`| `services/auth-service/.env`                 | —                                 |
| `TOTP_ENCRYPTION_KEY`        | `services/auth-service/.env`                 | —                                 |
| `SMTP_PASSWORD` (Gmail/SES)  | `services/auth-service/.env`                 | — (external provider)             |

`git ls-files | grep -E '\.env'` should return **only** `.env.example` files.
If it lists a real `.env`, stop and remove from history per Step 9 below.

---

## 1. Revoke external credentials FIRST

Before regenerating anything locally, invalidate anything that an outsider
could still abuse right now:

1. **Gmail App Password** (if SMTP uses Gmail)
   1. Open <https://myaccount.google.com/apppasswords>.
   2. Click the trash icon next to the "Backend Platform" entry.
   3. You will create a replacement in Step 5 below.
2. **AWS SES / other SMTP provider** — rotate SMTP credentials in the provider
   console. Capture the new secret in a password manager first, *then* revoke
   the old one.
3. **Managed DB / Redis** (RDS, ElastiCache, etc.) — if the current DB/Redis
   password is in use anywhere beyond this dev box, rotate via the provider's
   console. Dev-only compose? Step 2 below handles that.

---

## 2. Regenerate all local dev secrets in one shot

The repo ships a generator that writes fresh random values to every `.env` and
preserves existing SMTP keys unless you tell it otherwise.

```bash
# Force regeneration of every env file with new random secrets.
# --force overwrites even when the file is non-empty.
.venv/bin/python infra/scripts/generate_dev_env.py --force
```

What it does:

- 4096-bit RSA keypair, written as `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` (with
  real newlines inside the PEM, wrapped in `"…"` so python-dotenv unescapes).
- Fresh `TOTP_ENCRYPTION_KEY` via `Fernet.generate_key()`.
- Three 48-byte peppers (`REFRESH_TOKEN_HASH_PEPPER`, `PRIVACY_KEY_PEPPER`,
  `PASSWORD_RESET_TOKEN_PEPPER`). The generator intentionally issues a
  **distinct** `PRIVACY_KEY_PEPPER` per service: each service hashes only
  local data (its own audit log, its own Redis rate-limit bucket, its own
  brute-force identifiers), so cross-service parity is neither required nor
  desirable (compromise of one pepper shouldn't help decode another
  service's digests).
- `AUTH_DB_PASSWORD`, `USER_DB_PASSWORD`, `REDIS_PASSWORD` — 24-byte
  url-safe values, stored both in `infra/compose/.env.compose` and
  expanded into `DATABASE_URL`/`REDIS_URL` in every service env.
- SMTP_* keys are preserved from the previous auth-service `.env` if they had
  non-empty values. Clear them explicitly if you want to drop the old relay:

  ```bash
  sed -i 's/^SMTP_PASSWORD=.*/SMTP_PASSWORD=/' services/auth-service/.env
  sed -i 's/^SMTP_USERNAME=.*/SMTP_USERNAME=/' services/auth-service/.env
  sed -i 's/^SMTP_FROM_EMAIL=.*/SMTP_FROM_EMAIL=/' services/auth-service/.env
  ```

Verify the regeneration landed:

```bash
# None of these should match the values from the leak.
grep ^AUTH_DB_PASSWORD infra/compose/.env.compose
grep ^USER_DB_PASSWORD infra/compose/.env.compose
grep ^REDIS_PASSWORD   infra/compose/.env.compose
grep ^TOTP_ENCRYPTION_KEY services/auth-service/.env
# Each of these should hold a different 48-byte value:
grep ^PRIVACY_KEY_PEPPER   services/auth-service/.env services/user-service/.env services/api-gateway/.env
```

The DB/Redis passwords embedded in `DATABASE_URL` / `REDIS_URL` inside each
service `.env` are regenerated in lockstep with `infra/compose/.env.compose`
so that the compose stack keeps working; they will not match the
pre-rotation values.

---

## 3. Reset all local stateful containers

Post-rotation state is unreadable: Postgres users kept old passwords, Redis
rejects old creds, any TOTP secret stored under the previous Fernet key is
permanently unreadable. Blow away the dev volumes and start over.

```bash
docker compose --env-file infra/compose/.env.compose \
  -f infra/compose/docker-compose.dev.yml down --volumes --remove-orphans

make up
make migrate-auth
make migrate-user
```

> **Data loss warning.** This wipes local dev databases and Redis state.
> It is the correct behaviour for dev. For staging/production see Section 7.

---

## 4. Apply the new SMTP credential (if rotated)

If you rotated Gmail or SES in Step 1:

1. Generate a new App Password (Gmail) or create a new SES SMTP user.
2. Put the new value in `services/auth-service/.env`:

   ```bash
   sed -i "s|^SMTP_PASSWORD=.*|SMTP_PASSWORD=YOUR_NEW_SECRET|" services/auth-service/.env
   sed -i "s|^SMTP_USERNAME=.*|SMTP_USERNAME=no-reply@example.com|" services/auth-service/.env
   sed -i "s|^SMTP_FROM_EMAIL=.*|SMTP_FROM_EMAIL=no-reply@example.com|" services/auth-service/.env
   ```
3. Restart `auth-service`:

   ```bash
   docker compose --env-file infra/compose/.env.compose \
     -f infra/compose/docker-compose.dev.yml up -d --force-recreate auth-service
   ```
4. Smoke-test delivery:

   ```bash
   curl -i -X POST http://127.0.0.1:8000/v1/auth/password/forgot \
     -H 'Content-Type: application/json' \
     -d '{"email":"test_dev@example.com"}'
   ```
   Expect `202 Accepted`, and check the inbox (or catchall) for a reset email.

---

## 5. Verify auth flow end to end

After Steps 2 and 3, every short-lived user artefact has been invalidated:
access tokens, refresh tokens, login challenges, TOTP secrets, backup codes.
Validate the flow comes back up cleanly:

```bash
# Register fresh test user and inspect cookie set-up.
curl -i -X POST http://127.0.0.1:8000/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"rotation_test@example.com","password":"RotateMe-1234!"}'

# Log in (returns HttpOnly cookies, not raw tokens).
curl -i -c /tmp/bp.jar -b /tmp/bp.jar -X POST \
  http://127.0.0.1:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"rotation_test@example.com","password":"RotateMe-1234!"}'

# Pull the CSRF token that JS would see, refresh via cookie.
CSRF=$(grep bp_csrf_token /tmp/bp.jar | awk '{print $7}')
curl -i -c /tmp/bp.jar -b /tmp/bp.jar -X POST \
  http://127.0.0.1:8000/v1/tokens/refresh \
  -H "X-CSRF-Token: ${CSRF}" -H 'Content-Type: application/json' -d '{}'
```

Expected: `200`, `set-cookie: bp_access_token=…; HttpOnly; …` appears on login
and refresh; payloads contain `{"auth":"cookie","expires_in":900,…}`.

---

## 6. Verify automated test suite

Peppers and policy changes affect HMAC outputs, so re-run everything to catch
any drift:

```bash
.venv/bin/python -m ruff check services shared
PYTHONPATH=services/auth-service      .venv/bin/python -m pytest -q services/auth-service/tests
PYTHONPATH=services/user-service      .venv/bin/python -m pytest -q services/user-service/tests
PYTHONPATH=services/api-gateway       .venv/bin/python -m pytest -q services/api-gateway/tests
PYTHONPATH=services/notification-service .venv/bin/python -m pytest -q services/notification-service/tests
PYTHONPATH=shared/python/src          .venv/bin/python -m pytest -q shared/python/tests
```

Everything must stay green.

---

## 7. What changes in staging / production

Production uses Docker secrets mounted from `./secrets/*` (see
`docs/deployment/aws-ec2.md`). Follow the procedure in
`docs/runbooks/rotate-jwt-keys.md` for the zero-downtime JWT roll.

For non-JWT secrets in production:

1. Generate new files into `./secrets/`:

   ```bash
   python3 -c "from cryptography.fernet import Fernet; \
     open('secrets/totp_fernet.key.new','wb').write(Fernet.generate_key())"
   python3 -c "import base64, secrets; \
     open('secrets/privacy_key_pepper.txt.new','w').write( \
       base64.urlsafe_b64encode(secrets.token_bytes(48)).decode())"
   # …repeat for the pepper / SMTP / DB / Redis files you need.
   ```
2. Move the new files into place atomically on the EC2 host:

   ```bash
   for f in secrets/*.new; do mv "$f" "${f%.new}"; done
   chmod 600 secrets/*
   ```
3. Recreate the consumers so they re-read `/run/secrets/*`:

   ```bash
   docker compose --env-file .env -f infra/compose/docker-compose.prod.yml \
     up -d --force-recreate --no-deps \
     auth-service user-service app
   ```
4. Watch for the startup banner; rotation of `TOTP_ENCRYPTION_KEY` invalidates
   stored 2FA secrets — users must re-enrol their TOTP. Announce the window.
5. `docs/runbooks/revoke-refresh-tokens.md` handles session invalidation if
   you want all users logged out after a pepper rotation.

---

## 8. Post-rotation checklist

- [ ] Old Gmail / SES credential disabled at provider
- [ ] Old JWT private key securely destroyed
- [ ] Old DB/Redis passwords overwritten on every host
- [ ] `PRIVACY_KEY_PEPPER` regenerated (per-service values, not shared)
- [ ] `docker compose ps` shows all services healthy
- [ ] Login + refresh + logout flow validated manually (Step 5)
- [ ] Full test suite green (Step 6)
- [ ] Password-reset mail delivered to a real inbox (Step 4)
- [ ] Backup of old secrets scrubbed from password manager once rollback window
      is over

---

## 9. If a secret ended up in git history

If `git log -p --all -- '**/*.env*'` shows real secrets, history rewrite is
mandatory:

```bash
pip install git-filter-repo
git filter-repo --invert-paths \
  --path services/auth-service/.env \
  --path services/user-service/.env \
  --path services/api-gateway/.env \
  --path infra/compose/.env.compose

# Destructive. Coordinate with every collaborator before pushing.
git push --force origin --all
git push --force origin --tags
```

Then perform Steps 1-6 above to replace the leaked values.

Report the incident to your security team even if the repo is private: the
commit may have been cloned to build caches, CI artefacts, or laptops.
