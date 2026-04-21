#!/usr/bin/env bash
# On EC2 (or any prod host with this repo): pull the latest revision and redeploy docker-compose.prod.
#
# Prerequisites: same as ec2_compose_up.sh — infra/compose/.env.compose, secrets/, Docker.
#
# Usage:
#   export CORS_ORIGINS="http://YOUR_PUBLIC_IP:8080,http://YOUR_PUBLIC_IP"
#   bash infra/scripts/ec2_update.sh
#
# Optional:
#   BRANCH=main  — git branch to checkout and pull (default: main).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

BRANCH="${BRANCH:-main}"

if [[ -z "${CORS_ORIGINS:-}" ]]; then
  echo "Set CORS_ORIGINS (comma-separated), e.g.:" >&2
  echo "  export CORS_ORIGINS=\"http://203.0.113.10:8080,http://203.0.113.10\"" >&2
  exit 1
fi

git fetch origin
git checkout "${BRANCH}"
git pull --ff-only "origin" "${BRANCH}"

exec bash "${ROOT}/infra/scripts/ec2_compose_up.sh"
