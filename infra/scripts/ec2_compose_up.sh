#!/usr/bin/env bash
# Full bring-up on a host with repo checkout, infra/compose/.env.compose, and secrets/ populated.
# Usage:
#   export CORS_ORIGINS="http://YOUR_PUBLIC_IP:8080,http://YOUR_PUBLIC_IP"
#   bash infra/scripts/ec2_compose_up.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

if [[ -z "${CORS_ORIGINS:-}" ]]; then
  echo "Set CORS_ORIGINS (comma-separated), e.g.:" >&2
  echo "  export CORS_ORIGINS=\"http://203.0.113.10:8080,http://203.0.113.10\"" >&2
  exit 1
fi

python3 infra/scripts/render_prod_env_from_secrets.py --cors-origins "${CORS_ORIGINS}"
rm -f infra/compose/docker-compose.override.yml

cd infra/compose
docker compose -f docker-compose.prod.yml --env-file .env.compose build
docker compose -f docker-compose.prod.yml --env-file .env.compose up -d
docker compose -f docker-compose.prod.yml --env-file .env.compose run --rm auth-service alembic upgrade head
docker compose -f docker-compose.prod.yml --env-file .env.compose run --rm user-service alembic upgrade head
docker compose -f docker-compose.prod.yml --env-file .env.compose up -d --force-recreate auth-service user-service api-gateway

echo "OK: stack is up. Gateway (default): http://127.0.0.1:\${GATEWAY_PORT:-8080}/ui/"
echo ""
echo "If auth-service shows password authentication failed for user auth_service:"
echo "  Postgres keeps the role password from the FIRST init of the volume; changing"
echo "  AUTH_DB_PASSWORD in .env.compose alone does not update the DB. Either restore the"
echo "  original AUTH_DB_PASSWORD, or (DESTRUCTIVE) remove volume postgres_auth_data after"
echo "  docker compose down, then bring the stack up again and re-run migrations."
