#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[2]


def _escape_multiline(value: str) -> str:
    return value.replace("\n", "\\n")


def _gen_private_public_pem() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _gen_secret(length_bytes: int = 48) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(length_bytes)).decode("utf-8")


def _gen_password(length_bytes: int = 24) -> str:
    # URL-safe alphabet, no separators requiring URL encoding in DSNs.
    return secrets.token_urlsafe(length_bytes)


def _write_if_allowed(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and path.stat().st_size > 0 and not force:
        print(f"skip   {path} (already exists, use --force to overwrite)")
        return
    path.write_text(content, encoding="utf-8")
    print(f"write  {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate secure local development env files for backend-platform.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing target files")
    args = parser.parse_args()

    private_pem, public_pem = _gen_private_public_pem()
    fernet_key = Fernet.generate_key().decode("utf-8")

    refresh_pepper = _gen_secret()
    auth_privacy_pepper = _gen_secret()
    user_privacy_pepper = _gen_secret()
    gateway_privacy_pepper = _gen_secret()
    reset_pepper = _gen_secret()

    auth_db_password = _gen_password(24)
    user_db_password = _gen_password(24)
    redis_password = _gen_password(24)

    auth_env = "\n".join(
        [
            "SERVICE_NAME=auth-service",
            "SERVICE_ENV=development",
            "SERVICE_PORT=8001",
            "CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "",
            f"DATABASE_URL=postgresql+asyncpg://auth_service:{auth_db_password}@postgres-auth:5432/auth_service",
            f"REDIS_URL=redis://:{redis_password}@redis:6379/0",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            "JWT_ACCESS_TTL_SECONDS=900",
            "JWT_REFRESH_TTL_SECONDS=2592000",
            f'JWT_PRIVATE_KEY="{_escape_multiline(private_pem)}"',
            f'JWT_PUBLIC_KEY="{_escape_multiline(public_pem)}"',
            "",
            f"REFRESH_TOKEN_HASH_PEPPER={refresh_pepper}",
            f"PRIVACY_KEY_PEPPER={auth_privacy_pepper}",
            f"PASSWORD_RESET_TOKEN_PEPPER={reset_pepper}",
            "",
            "TOTP_ISSUER=Backend Platform",
            f"TOTP_ENCRYPTION_KEY={fernet_key}",
            "TOTP_CODE_DIGITS=6",
            "TOTP_INTERVAL_SECONDS=30",
            "",
            "LOGIN_CHALLENGE_TTL_SECONDS=300",
            "PASSWORD_RESET_TOKEN_TTL_SECONDS=900",
            "SMTP_HOST=",
            "SMTP_PORT=587",
            "SMTP_USERNAME=",
            "SMTP_PASSWORD=",
            "SMTP_USE_TLS=true",
            "SMTP_FROM_EMAIL=",
            "",
            "RATE_LIMIT_LOGIN_PER_MINUTE=10",
            "RATE_LIMIT_2FA_PER_MINUTE=10",
            "RATE_LIMIT_REFRESH_PER_MINUTE=30",
            "RATE_LIMIT_REGISTER_PER_MINUTE=5",
            "RATE_LIMIT_PASSWORD_RESET_PER_MINUTE=5",
            "",
            "BRUTE_FORCE_LOGIN_MAX_ATTEMPTS=5",
            "BRUTE_FORCE_LOGIN_WINDOW_SECONDS=300",
            "BRUTE_FORCE_LOGIN_LOCK_SECONDS=900",
            "BRUTE_FORCE_2FA_MAX_ATTEMPTS=5",
            "BRUTE_FORCE_2FA_WINDOW_SECONDS=300",
            "BRUTE_FORCE_2FA_LOCK_SECONDS=900",
            "BRUTE_FORCE_PASSWORD_RESET_MAX_ATTEMPTS=5",
            "BRUTE_FORCE_PASSWORD_RESET_WINDOW_SECONDS=300",
            "BRUTE_FORCE_PASSWORD_RESET_LOCK_SECONDS=900",
            "",
            "ARGON2_TIME_COST=3",
            "ARGON2_MEMORY_COST=65536",
            "ARGON2_PARALLELISM=4",
            "ARGON2_HASH_LENGTH=32",
            "ARGON2_SALT_LENGTH=16",
            "",
        ]
    )

    user_env = "\n".join(
        [
            "SERVICE_NAME=user-service",
            "SERVICE_ENV=development",
            "SERVICE_PORT=8002",
            "CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "",
            f"DATABASE_URL=postgresql+asyncpg://user_service:{user_db_password}@postgres-user:5432/user_service",
            f"REDIS_URL=redis://:{redis_password}@redis:6379/1",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            f'JWT_PUBLIC_KEY="{_escape_multiline(public_pem)}"',
            f"PRIVACY_KEY_PEPPER={user_privacy_pepper}",
            "",
            "RATE_LIMIT_PROFILE_WRITE_PER_MINUTE=30",
            "RATE_LIMIT_ROLES_WRITE_PER_MINUTE=10",
            "",
        ]
    )

    gateway_env = "\n".join(
        [
            "SERVICE_NAME=api-gateway",
            "SERVICE_ENV=development",
            "SERVICE_PORT=8000",
            "CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000",
            "",
            f"REDIS_URL=redis://:{redis_password}@redis:6379/2",
            "AUTH_SERVICE_URL=http://auth-service:8001",
            "USER_SERVICE_URL=http://user-service:8002",
            "NOTIFICATION_SERVICE_URL=",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            f'JWT_PUBLIC_KEY="{_escape_multiline(public_pem)}"',
            f"PRIVACY_KEY_PEPPER={gateway_privacy_pepper}",
            "",
            "UPSTREAM_TIMEOUT_SECONDS=10",
            "TRUSTED_PROXY_IPS=",
            "RATE_LIMIT_PUBLIC_AUTH_PER_MINUTE=30",
            "RATE_LIMIT_PROTECTED_PER_MINUTE=120",
            "",
        ]
    )

    compose_env = "\n".join(
        [
            "COMPOSE_PROJECT_NAME=backend-platform",
            f"AUTH_DB_PASSWORD={auth_db_password}",
            f"USER_DB_PASSWORD={user_db_password}",
            f"REDIS_PASSWORD={redis_password}",
            "GATEWAY_PORT=8080",
            "",
        ]
    )

    _write_if_allowed(ROOT / "services" / "auth-service" / ".env", auth_env, force=args.force)
    _write_if_allowed(ROOT / "services" / "user-service" / ".env", user_env, force=args.force)
    _write_if_allowed(ROOT / "services" / "api-gateway" / ".env", gateway_env, force=args.force)
    _write_if_allowed(ROOT / "infra" / "compose" / ".env.compose", compose_env, force=args.force)


if __name__ == "__main__":
    main()
