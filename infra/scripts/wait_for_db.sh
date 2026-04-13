#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-localhost}"
PORT="${2:-5432}"
USER_NAME="${3:-postgres}"
DB_NAME="${4:-postgres}"
TIMEOUT_SECONDS="${5:-60}"

START_TS="$(date +%s)"

while true; do
  if pg_isready -h "${HOST}" -p "${PORT}" -U "${USER_NAME}" -d "${DB_NAME}" >/dev/null 2>&1; then
    echo "Database ${DB_NAME} at ${HOST}:${PORT} is ready"
    exit 0
  fi

  NOW_TS="$(date +%s)"
  ELAPSED="$((NOW_TS - START_TS))"
  if [ "${ELAPSED}" -ge "${TIMEOUT_SECONDS}" ]; then
    echo "Timeout waiting for database ${DB_NAME} at ${HOST}:${PORT}" >&2
    exit 1
  fi

  sleep 2
done
