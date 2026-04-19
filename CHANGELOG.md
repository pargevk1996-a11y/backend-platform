# Changelog

All notable changes to this project are documented here. Follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] — production-readiness audit

Landed as 6 logical batches on top of `492571f`. Sum: 33 files modified, 11
files added, 4 files deleted, ~1500 LOC of net diff, 27 new tests.

### Added

- **Multi-stage production `Dockerfile`** at repo root with targets
  `auth-service`, `user-service`, `api-gateway`, `notification-service`. Builds
  wheels from `requirements.lock`, upgrades OS packages, runs as uid 10000
  under `tini`, ships with in-container `HEALTHCHECK`.
- **`shared-python` workspace package** with the truly-duplicated utilities
  (`stable_hmac_digest`, `normalize_optional`, `is_trusted_proxy`,
  `get_client_ip`, `extract_bearer_token`, `load_file_backed_env`) plus 16 unit
  tests. Consumed by `auth-service`, `user-service`, `api-gateway` via the
  new `shared-wheel` build stage and a `.pth` link in the dev venv.
- **Docker secrets flow** across `infra/compose/docker-compose.prod.yml`:
  RSA keys, Fernet key, peppers, SMTP password, DB/Redis passwords are now
  injected as `/run/secrets/*` files and read through a `<FIELD>_FILE`
  convention on each Pydantic `Settings` class. Eliminates `\n`-escape risks
  for PEM env vars.
- **Global IP rate-limit** on the gateway (`RATE_LIMIT_GLOBAL_PER_MINUTE`)
  applied before any scope-specific bucket.
- **Body cap** on the proxy path (2 MiB) with streaming check, so even without
  Nginx in front the gateway refuses oversized payloads.
- **`touch_session` debounce** via Redis `SET NX EX` — one upstream touch per
  sid per 60s instead of per request.
- **`pg_advisory_xact_lock`** around the RBAC seed in `user-service` lifespan,
  serialising startup across horizontally-scaled replicas.
- **Docker secrets CI support**: `.github/workflows/{deploy,security}.yml`
  rebuilt on `docker/build-push-action@v6` with `target:` matrix and GHA
  layer cache.
- **Runbook** `docs/runbooks/rotate-local-dev-secrets.md` with a step-by-step
  recovery procedure for a leaked local dev `.env`.
- **Deployment guide** `docs/deployment/aws-ec2.md` with turnkey secret
  provisioning script.
- **27 new tests**:
  - `services/auth-service/tests/unit/test_config_file_secrets.py` (3) — Docker
    secrets `_FILE` override, including PEM round-trip with real newlines.
  - `services/auth-service/tests/unit/test_password_service.py` (4 new) —
    min-length boundary, max-length cap, class-count below/at the threshold.
  - `services/api-gateway/tests/unit/test_rate_limit.py` (4) — limit threshold,
    per-scope isolation, per-IP isolation, HMAC of IP in the key.
  - `shared/python/tests/*` (16) — all new shared helpers.

### Changed

- **Gateway cookies** (`services/api-gateway/app/core/cookies.py`)
  - `domain=""` is no longer forwarded to Starlette (it used to raise).
  - `expires_in` from upstream is now clamped to
    `settings.auth_access_cookie_max_age_seconds` and coerced to `int`.
- **Password policy** raised to `>=12` chars / `<=128` chars /
  `>=3` character classes (lower/upper/digit/symbol).
- **2FA brute-force reset** also cleared on successful password reset, so a
  compromised account fully unlocks after the user changes the password.
- **TOTP verification** now uses `SELECT … FOR UPDATE` on the secret row,
  closing a race where two concurrent `/login/2fa` calls with the same code
  could both pass in the same 30-second window.
- **Email audit PII** replaced with HMAC digest (`email_digest`) in every
  auth-service audit payload — GDPR-friendly.
- **Internal hostnames** removed from gateway `/v1/health/ready` failure
  payloads. The real URL is now written to the structured server log only.
- **DB pool settings** in `auth-service`/`user-service` are now overridable
  via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`,
  `DB_CONNECT_TIMEOUT`. Defaults tightened to 10/5/5/1800/10.
- **CORSMiddleware** removed from `auth-service` and `user-service` — they
  are internal and must never be reached by a browser.
- **Gateway response rebuild** now strips upstream `Content-Length`,
  `Content-Encoding`, and `Transfer-Encoding` headers before returning the
  mutated token-issuing body to the client.
- **Login challenge payloads** in Redis are now type-checked on read: foreign
  / legacy entries are ignored instead of crashing with a 500.
- **`rate_limit_dependency`** takes the Settings attribute name (`str`), not
  a baked-in integer. Resolving the limit at request time removes the last
  reason to have `settings = get_settings()` at module level in API files.
- **`StaticFiles` mount** in the gateway resolved via `Path(__file__).resolve()`
  instead of the process CWD.
- **Login invariant violations** now emit structured
  `auth.login_invariant_violation` log events before raising `RuntimeError`,
  making alerting trivial.
- **`make test`** and **`make lint`** now include the `shared/python`
  workspace. Aggregate targets `make test`, `make lint`, and
  [new] `make ci` make it trivial to mirror the CI contract locally.
- **Single `Dockerfile` source of truth**: dev `docker-compose.dev.yml` now
  builds from the root `Dockerfile --target <svc>` the same way prod does.

### Removed

- `infra/docker/auth-service.Dockerfile`
- `infra/docker/user-service.Dockerfile`
- `infra/docker/gateway.Dockerfile`
- `infra/docker/notification-service.Dockerfile`
  (replaced by targets in the root `Dockerfile`).
- Duplicate `stable_hmac_digest` / `normalize_optional` / `get_client_ip` /
  `is_trusted_proxy` / `extract_bearer_token` / `_load_file_backed_env`
  definitions from each service's `core/` tree (now single-sourced in
  `shared.*`).

### Security

- Closed one HIGH race-condition on TOTP verification (parallel `/login/2fa`
  with the same code).
- Closed one HIGH PII leak vector (plaintext email in audit events).
- Closed one HIGH DoS vector (proxy reading unbounded request body before
  authentication).
- Closed one HIGH privacy vector (internal service URLs in public error
  payloads).
- Eliminated secrets-in-env transport risk for PEM keys by switching to
  Docker secrets + file-backed Pydantic fields.
- `_FILE`-backed helper is tested both for happy path and for graceful
  fallback when the path is unset or unreadable.

### Upgrade notes

- **Breaking:** Docker-compose in production now expects a `./secrets/`
  directory next to the compose file containing the files listed in
  `.env.example`. See `docs/deployment/aws-ec2.md` for a turnkey generation
  script.
- **Breaking for downstream tools:** auth-service audit payloads carry
  `email_digest` (sha256 HMAC with `PRIVACY_KEY_PEPPER`) instead of `email`.
- **Operational:** password policy tightened — any local password shorter
  than 12 chars or with fewer than 3 character classes will be rejected on
  next sign-up / password reset.

### Verification

- `make lint` — all 5 zones pass (services + shared).
- `make test` — 97 tests pass (41 auth / 12 user / 25 gateway / 3
  notification / 16 shared).
- `docker compose -f infra/compose/docker-compose.prod.yml config --quiet` —
  validates with the new secrets schema.
- `docker compose -f infra/compose/docker-compose.dev.yml config --quiet` —
  builds from the root `Dockerfile`.
