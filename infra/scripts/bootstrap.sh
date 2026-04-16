#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/pip install -r services/auth-service/requirements.lock
.venv/bin/pip install -r services/user-service/requirements.lock
.venv/bin/pip install -r services/api-gateway/requirements.lock
.venv/bin/pip install -r tests/e2e/requirements.txt

chmod +x infra/scripts/generate_dev_env.py

need_generate=0
force_regenerate=0

if [ ! -s "services/auth-service/.env" ] || [ ! -s "services/user-service/.env" ] || [ ! -s "services/api-gateway/.env" ] || [ ! -s "infra/compose/.env.compose" ]; then
  need_generate=1
else
  if grep -Eq '^DATABASE_URL=postgresql\+asyncpg://auth_service:auth_service@postgres-auth:5432/auth_service$' services/auth-service/.env \
    || grep -Eq '^DATABASE_URL=postgresql\+asyncpg://user_service:user_service@postgres-user:5432/user_service$' services/user-service/.env \
    || grep -Eq '^REDIS_URL=redis://redis:6379/0$' services/auth-service/.env \
    || grep -Eq '^REDIS_URL=redis://redis:6379/1$' services/user-service/.env \
    || grep -Eq '^REDIS_URL=redis://redis:6379/2$' services/api-gateway/.env \
    || ! grep -Eq '^AUTH_DB_PASSWORD=.+' infra/compose/.env.compose \
    || ! grep -Eq '^USER_DB_PASSWORD=.+' infra/compose/.env.compose \
    || ! grep -Eq '^REDIS_PASSWORD=.+' infra/compose/.env.compose; then
    need_generate=1
    force_regenerate=1
  fi
fi

if [ "${need_generate}" -eq 1 ]; then
  generate_args=()
  if [ "${force_regenerate}" -eq 1 ]; then
    echo "Detected legacy insecure connection defaults in env files. Regenerating secure env files."
    generate_args+=(--force)
  fi
  .venv/bin/python infra/scripts/generate_dev_env.py "${generate_args[@]}"
else
  echo "Env files already exist and are non-empty. Skipping generation."
fi

echo "Bootstrap complete."
