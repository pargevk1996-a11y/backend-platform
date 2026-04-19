#!/usr/bin/env python3
"""Build services/*/.env from infra/compose/.env.compose + repo secrets/ (EC2 / bare-metal)."""

from __future__ import annotations

import argparse
from pathlib import Path


def _escape_pem(value: str) -> str:
    return value.replace("\n", "\\n")


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: auto)",
    )
    parser.add_argument(
        "--compose-env",
        type=Path,
        help="Path to infra/compose/.env.compose (default: <repo>/infra/compose/.env.compose)",
    )
    parser.add_argument(
        "--cors-origins",
        required=True,
        help="Comma-separated CORS origins (e.g. http://1.2.3.4:8080,http://1.2.3.4)",
    )
    args = parser.parse_args()

    root: Path = args.repo_root
    compose_path = args.compose_env or (root / "infra" / "compose" / ".env.compose")
    secrets_dir = root / "secrets"

    if not compose_path.is_file():
        raise SystemExit(f"Missing {compose_path}")
    for name in (
        "jwt_private.pem",
        "jwt_public.pem",
        "refresh_token_pepper.txt",
        "privacy_key_pepper.txt",
        "password_reset_pepper.txt",
        "totp_fernet.key",
    ):
        if not (secrets_dir / name).is_file():
            raise SystemExit(f"Missing secret file: {secrets_dir / name}")

    compose = _parse_dotenv(compose_path)
    try:
        auth_db = compose["AUTH_DB_PASSWORD"]
        user_db = compose["USER_DB_PASSWORD"]
        redis_pw = compose["REDIS_PASSWORD"]
    except KeyError as exc:
        raise SystemExit(f".env.compose missing key: {exc!s}") from exc

    priv_pem = _read_text(secrets_dir / "jwt_private.pem")
    pub_pem = _read_text(secrets_dir / "jwt_public.pem")
    refresh_pepper = _read_text(secrets_dir / "refresh_token_pepper.txt")
    privacy_pepper = _read_text(secrets_dir / "privacy_key_pepper.txt")
    reset_pepper = _read_text(secrets_dir / "password_reset_pepper.txt")
    totp_key = _read_text(secrets_dir / "totp_fernet.key")

    smtp_pw_path = secrets_dir / "smtp_password.txt"
    smtp_password = _read_text(smtp_pw_path) if smtp_pw_path.is_file() else ""

    cors = ",".join(p.strip() for p in args.cors_origins.split(",") if p.strip())

    auth_env = "\n".join(
        [
            "SERVICE_NAME=auth-service",
            "SERVICE_ENV=production",
            "SERVICE_PORT=8001",
            f"CORS_ALLOWED_ORIGINS={cors}",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "",
            f"DATABASE_URL=postgresql+asyncpg://auth_service:{auth_db}@postgres-auth:5432/auth_service",
            f"REDIS_URL=redis://:{redis_pw}@redis:6379/0",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            "JWT_ACCESS_TTL_SECONDS=900",
            "JWT_REFRESH_TTL_SECONDS=2592000",
            f'JWT_PRIVATE_KEY="{_escape_pem(priv_pem)}"',
            f'JWT_PUBLIC_KEY="{_escape_pem(pub_pem)}"',
            "",
            f"REFRESH_TOKEN_HASH_PEPPER={refresh_pepper}",
            f"PRIVACY_KEY_PEPPER={privacy_pepper}",
            f"PASSWORD_RESET_TOKEN_PEPPER={reset_pepper}",
            "",
            "TOTP_ISSUER=Backend Platform",
            f"TOTP_ENCRYPTION_KEY={totp_key}",
            "TOTP_CODE_DIGITS=6",
            "TOTP_INTERVAL_SECONDS=30",
            "",
            "LOGIN_CHALLENGE_TTL_SECONDS=300",
            "PASSWORD_RESET_TOKEN_TTL_SECONDS=900",
            "SMTP_HOST=",
            "SMTP_PORT=587",
            "SMTP_USERNAME=",
            f"SMTP_PASSWORD={smtp_password}",
            "SMTP_REQUIRE_DELIVERY=false",
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
            "SERVICE_ENV=production",
            "SERVICE_PORT=8002",
            f"CORS_ALLOWED_ORIGINS={cors}",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "",
            f"DATABASE_URL=postgresql+asyncpg://user_service:{user_db}@postgres-user:5432/user_service",
            f"REDIS_URL=redis://:{redis_pw}@redis:6379/1",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            f'JWT_PUBLIC_KEY="{_escape_pem(pub_pem)}"',
            f"PRIVACY_KEY_PEPPER={privacy_pepper}",
            "",
            "RATE_LIMIT_PROFILE_WRITE_PER_MINUTE=30",
            "RATE_LIMIT_ROLES_WRITE_PER_MINUTE=10",
            "",
        ]
    )

    gateway_env = "\n".join(
        [
            "SERVICE_NAME=api-gateway",
            "SERVICE_ENV=production",
            "SERVICE_PORT=8000",
            f"CORS_ALLOWED_ORIGINS={cors}",
            "",
            f"REDIS_URL=redis://:{redis_pw}@redis:6379/2",
            "AUTH_SERVICE_URL=http://auth-service:8001",
            "USER_SERVICE_URL=http://user-service:8002",
            "NOTIFICATION_SERVICE_URL=",
            "",
            "JWT_ALGORITHM=RS256",
            "JWT_ISSUER=backend-platform",
            "JWT_AUDIENCE=backend-clients",
            f'JWT_PUBLIC_KEY="{_escape_pem(pub_pem)}"',
            f"PRIVACY_KEY_PEPPER={privacy_pepper}",
            "",
            "UPSTREAM_TIMEOUT_SECONDS=10",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "RATE_LIMIT_PUBLIC_AUTH_PER_MINUTE=30",
            "RATE_LIMIT_PROTECTED_PER_MINUTE=120",
            "",
        ]
    )

    (root / "services" / "auth-service" / ".env").write_text(auth_env, encoding="utf-8")
    (root / "services" / "user-service" / ".env").write_text(user_env, encoding="utf-8")
    (root / "services" / "api-gateway" / ".env").write_text(gateway_env, encoding="utf-8")
    print(f"Wrote services/*/ .env with CORS_ALLOWED_ORIGINS={cors}")


if __name__ == "__main__":
    main()
