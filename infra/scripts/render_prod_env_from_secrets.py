#!/usr/bin/env python3
"""Build services/*/.env from infra/compose/.env.compose + repo secrets/ (EC2 / bare-metal)."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import quote_plus


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


def _read_optional_one_line(path: Path) -> str:
    if not path.is_file():
        return ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            return s
    return ""


def _compose_get(compose: dict[str, str], key: str) -> str:
    return (compose.get(key) or "").strip()


def _quote_env_value(val: str) -> str:
    """Quote .env values that contain spaces, #, or quotes (safe for SMTP app passwords)."""
    if not val:
        return ""
    if any(c in val for c in ' "\n\\#'):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return val


def _resolve_smtp_for_auth_env(compose: dict[str, str], secrets_dir: Path) -> dict[str, str]:
    """Merge SMTP from infra/compose/.env.compose + optional secrets/*.txt (no secrets printed)."""
    app_pw_path = secrets_dir / "smtp_app_password.txt"
    legacy_pw_path = secrets_dir / "smtp_password.txt"
    smtp_password = ""
    if app_pw_path.is_file():
        smtp_password = _read_text(app_pw_path)
    if not smtp_password and legacy_pw_path.is_file():
        smtp_password = _read_text(legacy_pw_path)
    if not smtp_password:
        smtp_password = _compose_get(compose, "SMTP_PASSWORD")

    smtp_host = _read_optional_one_line(secrets_dir / "smtp_host.txt") or _compose_get(
        compose, "SMTP_HOST"
    )
    smtp_username = _read_optional_one_line(secrets_dir / "smtp_username.txt") or _compose_get(
        compose, "SMTP_USERNAME"
    )
    smtp_from_email = (
        _read_optional_one_line(secrets_dir / "smtp_from_email.txt")
        or _compose_get(compose, "SMTP_FROM_EMAIL")
        or smtp_username
    )
    smtp_from_name = (
        _read_optional_one_line(secrets_dir / "smtp_from_name.txt")
        or _compose_get(compose, "SMTP_FROM_NAME")
        or "Backend Platform"
    )
    identity_fallback = _read_optional_one_line(secrets_dir / "smtp_identity_email.txt")
    if not smtp_username and identity_fallback:
        smtp_username = identity_fallback
    if not smtp_from_email and identity_fallback:
        smtp_from_email = identity_fallback

    if smtp_password and not smtp_host:
        smtp_host = "smtp.gmail.com"

    smtp_port = _compose_get(compose, "SMTP_PORT") or "587"
    tls_raw = _compose_get(compose, "SMTP_USE_TLS").lower()
    if tls_raw in ("false", "0", "no"):
        smtp_use_tls = "false"
    else:
        smtp_use_tls = "true"

    smtp_require = _compose_get(compose, "SMTP_REQUIRE_DELIVERY")
    if not smtp_require:
        smtp_require = "true"

    allow_raw = _compose_get(compose, "AUTH_ALLOW_MISSING_SMTP").lower()
    if allow_raw in ("true", "1", "yes"):
        auth_allow_missing = "true"
    elif allow_raw in ("false", "0", "no"):
        auth_allow_missing = "false"
    else:
        delivery_ready = bool(smtp_host and (smtp_from_email or smtp_username) and smtp_password)
        auth_allow_missing = "false" if delivery_ready else "true"

    return {
        "SMTP_HOST": _quote_env_value(smtp_host) if smtp_host else "",
        "SMTP_PORT": smtp_port,
        "SMTP_USERNAME": _quote_env_value(smtp_username) if smtp_username else "",
        "SMTP_PASSWORD": _quote_env_value(smtp_password) if smtp_password else "",
        "SMTP_USE_TLS": smtp_use_tls,
        "SMTP_FROM_EMAIL": _quote_env_value(smtp_from_email) if smtp_from_email else "",
        "SMTP_FROM_NAME": _quote_env_value(smtp_from_name) if smtp_from_name else "",
        "SMTP_REQUIRE_DELIVERY": smtp_require,
        "AUTH_ALLOW_MISSING_SMTP": auth_allow_missing,
    }


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

    smtp_lines = _resolve_smtp_for_auth_env(compose, secrets_dir)
    login_max = (
        _compose_get(compose, "LOGIN_MAX_FAILED_ATTEMPTS")
        or _compose_get(compose, "BRUTE_FORCE_LOGIN_MAX_ATTEMPTS")
        or "3"
    )
    reset_max = (
        _compose_get(compose, "RESET_CODE_MAX_FAILED_ATTEMPTS")
        or _compose_get(compose, "BRUTE_FORCE_PASSWORD_RESET_MAX_ATTEMPTS")
        or "3"
    )
    support_email_raw = _compose_get(compose, "SUPPORT_EMAIL")
    if support_email_raw:
        support_email_line = f"SUPPORT_EMAIL={_quote_env_value(support_email_raw)}"
    else:
        support_email_line = "SUPPORT_EMAIL="

    cors = ",".join(p.strip() for p in args.cors_origins.split(",") if p.strip())

    auth_db_q = quote_plus(auth_db, safe="")
    user_db_q = quote_plus(user_db, safe="")
    redis_pw_q = quote_plus(redis_pw, safe="")

    auth_env = "\n".join(
        [
            "SERVICE_NAME=auth-service",
            "SERVICE_ENV=production",
            "SERVICE_PORT=8001",
            f"CORS_ALLOWED_ORIGINS={cors}",
            "TRUSTED_PROXY_IPS=172.16.0.0/12",
            "",
            f"DATABASE_URL=postgresql+asyncpg://auth_service:{auth_db_q}@postgres-auth:5432/auth_service",
            f"REDIS_URL=redis://:{redis_pw_q}@redis:6379/0",
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
            f"SMTP_HOST={smtp_lines['SMTP_HOST']}",
            f"SMTP_PORT={smtp_lines['SMTP_PORT']}",
            f"SMTP_USERNAME={smtp_lines['SMTP_USERNAME']}",
            f"SMTP_PASSWORD={smtp_lines['SMTP_PASSWORD']}",
            f"SMTP_USE_TLS={smtp_lines['SMTP_USE_TLS']}",
            f"SMTP_FROM_EMAIL={smtp_lines['SMTP_FROM_EMAIL']}",
            f"SMTP_FROM_NAME={smtp_lines['SMTP_FROM_NAME']}",
            f"SMTP_REQUIRE_DELIVERY={smtp_lines['SMTP_REQUIRE_DELIVERY']}",
            f"AUTH_ALLOW_MISSING_SMTP={smtp_lines['AUTH_ALLOW_MISSING_SMTP']}",
            support_email_line,
            "",
            "RATE_LIMIT_LOGIN_PER_MINUTE=10",
            "RATE_LIMIT_2FA_PER_MINUTE=10",
            "RATE_LIMIT_REFRESH_PER_MINUTE=30",
            "RATE_LIMIT_REGISTER_PER_MINUTE=5",
            "RATE_LIMIT_PASSWORD_RESET_PER_MINUTE=5",
            "",
            f"BRUTE_FORCE_LOGIN_MAX_ATTEMPTS={login_max}",
            "BRUTE_FORCE_LOGIN_WINDOW_SECONDS=300",
            "BRUTE_FORCE_LOGIN_LOCK_SECONDS=900",
            "BRUTE_FORCE_2FA_MAX_ATTEMPTS=5",
            "BRUTE_FORCE_2FA_WINDOW_SECONDS=300",
            "BRUTE_FORCE_2FA_LOCK_SECONDS=900",
            f"BRUTE_FORCE_PASSWORD_RESET_MAX_ATTEMPTS={reset_max}",
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
            f"DATABASE_URL=postgresql+asyncpg://user_service:{user_db_q}@postgres-user:5432/user_service",
            f"REDIS_URL=redis://:{redis_pw_q}@redis:6379/1",
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
            f"REDIS_URL=redis://:{redis_pw_q}@redis:6379/2",
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
