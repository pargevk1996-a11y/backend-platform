#!/usr/bin/env bash
# EC2 / prod host: диагностика HttpOnly refresh-куки (BFF) по плану ops.
# Запускать с корня клона репозитория (рядом с infra/, services/), на машине где уже поднят prod compose:
#
#   ssh -i KEY.pem ubuntu@YOUR_EC2_IP
#   cd ~/backend-platform   # ваш путь
#   bash infra/scripts/ec2_diagnose_refresh_cookie.sh
#
# Опционально проверить Set-Cookie на login (нужны тестовые учётные данные):
#   export DIAGNOSE_LOGIN_EMAIL='user@example.com'
#   export DIAGNOSE_LOGIN_PASSWORD='your-password'
#   bash infra/scripts/ec2_diagnose_refresh_cookie.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

COMPOSE_DIR="${ROOT}/infra/compose"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.prod.yml"
ENV_COMPOSE="${COMPOSE_DIR}/.env.compose"
GATEWAY_ENV="${ROOT}/services/api-gateway/.env"

echo "=== ec2_diagnose_refresh_cookie ==="
echo "Repo: ${ROOT}"
echo ""

if [[ ! -f "${COMPOSE_FILE}" || ! -f "${ENV_COMPOSE}" ]]; then
  echo "ERROR: missing ${COMPOSE_FILE} or ${ENV_COMPOSE}" >&2
  exit 1
fi

# shellcheck source=/dev/null
GATEWAY_PORT=8080
if [[ -f "${ENV_COMPOSE}" ]]; then
  line="$(grep -E '^[[:space:]]*GATEWAY_PORT=' "${ENV_COMPOSE}" | tail -1 || true)"
  if [[ -n "${line}" ]]; then
    GATEWAY_PORT="${line#*=}"
    GATEWAY_PORT="${GATEWAY_PORT//[$'\r']}"
  fi
fi

echo "--- 1) Git (deployed checkout on disk) ---"
if [[ -d "${ROOT}/.git" ]]; then
  git -C "${ROOT}" rev-parse HEAD
  git -C "${ROOT}" log -1 --oneline
else
  echo "(no .git — skip)"
fi
echo ""

echo "--- 2) Docker: api-gateway container ---"
cd "${COMPOSE_DIR}"
if ! docker compose -f docker-compose.prod.yml --env-file .env.compose ps api-gateway 2>/dev/null; then
  echo "WARN: docker compose ps failed (daemon down or not logged in?)" >&2
else
  cid="$(docker compose -f docker-compose.prod.yml --env-file .env.compose ps -q api-gateway 2>/dev/null || true)"
  if [[ -n "${cid}" ]]; then
    echo "Image / started:"
    docker inspect -f '{{.Config.Image}} created={{.Created}} status={{.State.Status}}' "${cid}" 2>/dev/null || true
  fi
fi
echo ""

echo "--- 3) api-gateway logs (missing refresh cookie / errors) ---"
docker compose -f docker-compose.prod.yml --env-file .env.compose logs --tail 400 api-gateway 2>/dev/null \
  | grep -E 'browser_auth_missing_refresh_cookie|ERROR|Exception|Traceback' || echo "(no matching lines in last 400 log lines)"
echo ""

echo "--- 4) services/api-gateway/.env (cookie / proxy / CORS-related keys only) ---"
if [[ -f "${GATEWAY_ENV}" ]]; then
  grep -i -E '^(REFRESH_COOKIE|TRUSTED_PROXY|CORS_|GATEWAY|SERVICE_ENV)=' "${GATEWAY_ENV}" 2>/dev/null || echo "(no matching keys)"
else
  echo "MISSING: ${GATEWAY_ENV}"
fi
echo ""

echo "--- 5) Optional: curl login → response headers (Set-Cookie) ---"
if [[ -n "${DIAGNOSE_LOGIN_EMAIL:-}" && -n "${DIAGNOSE_LOGIN_PASSWORD:-}" ]]; then
  hdrf="$(mktemp)"
  bodyf="$(mktemp)"
  # shellcheck disable=SC2064
  trap 'rm -f "${hdrf}" "${bodyf}"' EXIT
  code="$(curl -sS -o "${bodyf}" -w '%{http_code}' -D "${hdrf}" -X POST "http://127.0.0.1:${GATEWAY_PORT}/v1/browser-auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${DIAGNOSE_LOGIN_EMAIL}\",\"password\":\"${DIAGNOSE_LOGIN_PASSWORD}\"}" || true)"
  echo "HTTP status: ${code}"
  echo "Set-Cookie lines from response headers:"
  grep -i '^set-cookie:' "${hdrf}" || echo "(none)"
  echo "Response body (first 200 chars):"
  head -c 200 "${bodyf}" || true
  echo ""
  rm -f "${hdrf}" "${bodyf}"
  trap - EXIT
else
  echo "Skipped (set DIAGNOSE_LOGIN_EMAIL and DIAGNOSE_LOGIN_PASSWORD to test)."
fi
echo ""

echo "--- 6) Browser (manual) — same-origin checklist ---"
echo "1. Open DevTools → Application → Cookies for the SAME origin as the address bar (scheme+host+port)."
echo "2. After sign-in, confirm cookie name (default bp_rt) exists for that origin."
echo "3. Network → POST .../browser-auth/refresh after reload → Request Headers must include Cookie: bp_rt=..."
echo "4. Gateway URL in the /ui form must match the page origin, or the cookie will not apply to XHR/fetch."
echo ""
echo "Done."
