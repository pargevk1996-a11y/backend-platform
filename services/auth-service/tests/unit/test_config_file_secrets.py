"""Verify that <FIELD>_FILE env vars override raw env values for secrets."""
from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import Settings
from cryptography.fernet import Fernet


def _build_minimal_env(tmp_path: Path) -> dict[str, str]:
    """Return a mapping containing just enough env for Settings() to construct."""
    # These values are placeholders used only when the corresponding _FILE env
    # variable is absent. The tests below always point the FILE vars at files
    # with the real expected contents.
    placeholder_pem = "-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----"
    placeholder_pepper = "x" * 48
    placeholder_fernet = Fernet.generate_key().decode()
    return {
        "SERVICE_NAME": "auth-service",
        "SERVICE_ENV": "development",
        "DATABASE_URL": "postgresql+asyncpg://u:p@h:5432/d",
        "REDIS_URL": "redis://h:6379/0",
        "JWT_PRIVATE_KEY": placeholder_pem,
        "JWT_PUBLIC_KEY": placeholder_pem,
        "REFRESH_TOKEN_HASH_PEPPER": placeholder_pepper,
        "PRIVACY_KEY_PEPPER": placeholder_pepper,
        "PASSWORD_RESET_TOKEN_PEPPER": placeholder_pepper,
        "TOTP_ENCRYPTION_KEY": placeholder_fernet,
    }


def _isolate_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    """Clear any real-secret env that may leak from the developer's shell."""
    for key in list(env.keys()) + [
        "JWT_PRIVATE_KEY_FILE",
        "JWT_PUBLIC_KEY_FILE",
        "TOTP_ENCRYPTION_KEY_FILE",
        "REFRESH_TOKEN_HASH_PEPPER_FILE",
        "PRIVACY_KEY_PEPPER_FILE",
        "PASSWORD_RESET_TOKEN_PEPPER_FILE",
        "SMTP_PASSWORD_FILE",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def test_file_backed_env_overrides_pepper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_path = tmp_path / "privacy_pepper.txt"
    file_content = "P" * 48
    secret_path.write_text(file_content + "\n", encoding="utf-8")

    env = _build_minimal_env(tmp_path)
    env["PRIVACY_KEY_PEPPER_FILE"] = str(secret_path)
    _isolate_env(monkeypatch, env)
    monkeypatch.chdir(tmp_path)  # avoid loading repo .env files

    settings = Settings()  # type: ignore[call-arg]

    # The FILE-backed content (trimmed of trailing newlines) must win over the
    # inline PRIVACY_KEY_PEPPER env var.
    assert settings.privacy_key_pepper.get_secret_value() == file_content


def test_file_backed_env_overrides_pem_with_real_newlines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pem = (
        "-----BEGIN PUBLIC KEY-----\n"
        "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAabc\n"
        "-----END PUBLIC KEY-----"
    )
    secret_path = tmp_path / "jwt_pub.pem"
    secret_path.write_text(pem, encoding="utf-8")

    env = _build_minimal_env(tmp_path)
    env["JWT_PUBLIC_KEY_FILE"] = str(secret_path)
    _isolate_env(monkeypatch, env)
    monkeypatch.chdir(tmp_path)

    settings = Settings()  # type: ignore[call-arg]

    # PEM must round-trip with real newlines, not the literal `\n` escape that
    # plain env-var transport through docker compose would produce.
    assert "\n" in settings.jwt_public_key.get_secret_value()
    assert settings.jwt_public_key.get_secret_value().startswith(
        "-----BEGIN PUBLIC KEY-----\n"
    )


def test_missing_file_path_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = _build_minimal_env(tmp_path)
    env["PRIVACY_KEY_PEPPER_FILE"] = str(tmp_path / "does_not_exist.txt")
    _isolate_env(monkeypatch, env)
    monkeypatch.chdir(tmp_path)

    # Missing files fall back to the raw env value without raising.
    settings = Settings()  # type: ignore[call-arg]
    assert settings.privacy_key_pepper.get_secret_value() == "x" * 48
