#!/usr/bin/env bash
set -euo pipefail

SECRETS_DIR="${1:-infra/secrets/jwt}"
KEY_PREFIX="${2:-auth-jwt}"
DATE_TAG="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${SECRETS_DIR}"
chmod 700 "${SECRETS_DIR}"

PRIVATE_KEY_PATH="${SECRETS_DIR}/${KEY_PREFIX}-${DATE_TAG}.private.pem"
PUBLIC_KEY_PATH="${SECRETS_DIR}/${KEY_PREFIX}-${DATE_TAG}.public.pem"

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096 -out "${PRIVATE_KEY_PATH}"
openssl rsa -pubout -in "${PRIVATE_KEY_PATH}" -out "${PUBLIC_KEY_PATH}"

chmod 600 "${PRIVATE_KEY_PATH}" "${PUBLIC_KEY_PATH}"

echo "Generated key pair:"
echo "  Private: ${PRIVATE_KEY_PATH}"
echo "  Public:  ${PUBLIC_KEY_PATH}"
echo
echo "Next steps:"
echo "1) Update JWT_PUBLIC_KEY in user-service/api-gateway env files"
echo "2) Update JWT_PRIVATE_KEY and JWT_PUBLIC_KEY in auth-service env"
echo "3) Roll out auth-service first, then user-service/api-gateway"
