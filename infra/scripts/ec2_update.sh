#!/usr/bin/env bash
# AWS (EC2): обновить код из GitHub и перезапустить prod stack (docker-compose.prod.yml).
# Нужен уже настроенный клон repo, infra/compose/.env.compose и каталог secrets/.
#
# Выполнять В КОРНЕ репозитория (например ~/backend-platform), не из ~:
#   cd ~/backend-platform
#
# Использование:
#   export CORS_ORIGINS="http://ВАSH_PUBLIC_IP:8080,http://ВАSH_PUBLIC_IP"
#   bash infra/scripts/ec2_update.sh
#
# Необязательно: BRANCH=main — ветка для checkout и pull (по умолчанию main).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

BRANCH="${BRANCH:-main}"

if [[ -z "${CORS_ORIGINS:-}" ]]; then
  echo "Задайте CORS_ORIGINS, например:" >&2
  echo '  export CORS_ORIGINS="http://203.0.113.10:8080,http://203.0.113.10"' >&2
  exit 1
fi

git fetch origin
git checkout "${BRANCH}"
git pull --ff-only "origin" "${BRANCH}"

exec bash "${ROOT}/infra/scripts/ec2_compose_up.sh"
