#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE="infra/compose/docker-compose.dev.yml"
COMPOSE_ENV="infra/compose/.env.compose"

cleanup() {
  docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" down --volumes --remove-orphans || true
}

wait_ready() {
  local url="$1"
  local retries="${2:-60}"
  local sleep_sec="${3:-2}"

  for ((i = 1; i <= retries; i++)); do
    if .venv/bin/python -c "import sys, urllib.request; response = urllib.request.urlopen(sys.argv[1], timeout=2); status = getattr(response, 'status', 0); sys.exit(0 if 200 <= status < 300 else 1)" "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${sleep_sec}"
  done
  echo "Timed out waiting for readiness: ${url}" >&2
  return 1
}

trap cleanup EXIT

bash infra/scripts/bootstrap.sh

# Start only infra dependencies first. App services depend on migrated schemas.
docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" up -d --build postgres-auth postgres-user redis

docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" run --rm auth-service alembic upgrade head
docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" run --rm user-service alembic upgrade head

docker compose --env-file "${COMPOSE_ENV}" -f "${COMPOSE_FILE}" up -d --build auth-service user-service api-gateway

wait_ready "http://localhost:8001/v1/health/ready"
wait_ready "http://localhost:8002/v1/health/ready"
wait_ready "http://localhost:8000/v1/health/ready"

GATEWAY_BASE_URL="${GATEWAY_BASE_URL:-http://localhost:8000}" \
  .venv/bin/python -m pytest -q tests/e2e/test_gateway_auth_security_flow.py
