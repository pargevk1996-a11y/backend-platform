from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app.core.config import Settings
from cryptography.fernet import Fernet
from pydantic import ValidationError


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://auth:auth@localhost:5432/auth")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "test-signing-key")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "test-signing-key")
    monkeypatch.setenv("REFRESH_TOKEN_HASH_PEPPER", "x" * 40)
    monkeypatch.setenv("PRIVACY_KEY_PEPPER", "y" * 40)
    monkeypatch.setenv("PASSWORD_RESET_TOKEN_PEPPER", "z" * 40)
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode("utf-8"))


def test_settings_reject_short_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("PRIVACY_KEY_PEPPER", "too-short")

    with pytest.raises(ValidationError):
        Settings()


def test_production_rejects_hs_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SERVICE_ENV", "production")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://app.example.com"]')

    with pytest.raises(ValidationError):
        Settings()


def test_smtp_from_email_falls_back_to_username(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "sixteen-char-appwd")
    # Do not inherit SMTP_FROM_* from a developer .env file in the service directory.
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    monkeypatch.setenv("SMTP_FROM_NAME", "")

    settings = Settings()

    assert settings.smtp_from_email_value == "mailer@example.com"
    assert settings.smtp_is_configured


def test_smtp_password_read_from_file_when_env_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_required_env(monkeypatch)
    pw_file = tmp_path / "smtp_password.txt"
    pw_file.write_text("sixteen-char-appwd\n", encoding="utf-8")
    # Prefer empty env password so .env cannot override the temp file in CI/dev.
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_PASSWORD_FILE", str(pw_file))
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.com")

    settings = Settings()

    assert settings.smtp_password_value == "sixteen-char-appwd"


def test_smtp_password_legacy_file_when_canonical_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Legacy secrets/smtp_password.txt still works if smtp_app_password.txt is absent."""
    _set_required_env(monkeypatch)
    legacy = tmp_path / "smtp_password.txt"
    legacy.write_text("sixteen-char-appwd\n", encoding="utf-8")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.delenv("SMTP_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "mailer@example.com")

    from app.core import config as config_module

    monkeypatch.setattr(config_module, "_DEFAULT_SMTP_APP_PASSWORD_FILE", tmp_path / "missing.txt")
    monkeypatch.setattr(config_module, "_LEGACY_SMTP_PASSWORD_FILE", legacy)

    settings = Settings()
    assert settings.smtp_password_value == "sixteen-char-appwd"


def test_smtp_ec2_defaults_identity_file_and_gmail_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Password file + identity fill mailbox; SMTP_HOST must come from env (no hardcoded provider)."""
    _set_required_env(monkeypatch)
    id_file = tmp_path / "smtp_identity_email.txt"
    id_file.write_text("shipper@gmail.com\n", encoding="utf-8")
    pw_file = tmp_path / "smtp_password.txt"
    pw_file.write_text("sixteen-char-appwd\n", encoding="utf-8")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.delenv("SMTP_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")

    from app.core import config as config_module

    monkeypatch.setattr(config_module, "_SMTP_IDENTITY_FILE", id_file)
    monkeypatch.setattr(config_module, "_DEFAULT_SMTP_APP_PASSWORD_FILE", pw_file)

    settings = Settings()

    assert settings.smtp_host == "smtp.gmail.com"
    assert settings.smtp_username == "shipper@gmail.com"
    assert settings.smtp_from_email == "shipper@gmail.com"
    assert settings.smtp_is_configured


def test_smtp_identity_file_permission_denied_does_not_crash_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EC2: root-only or unreadable smtp_identity_email.txt must not kill Settings()."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SMTP_USERNAME", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    from app.core import config as config_module

    bad = MagicMock()
    bad.read_text.side_effect = PermissionError(13, "Permission denied")
    monkeypatch.setattr(config_module, "_SMTP_IDENTITY_FILE", bad)

    settings = Settings()
    assert settings.smtp_username is None


def test_development_requires_delivery_when_smtp_is_partially_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    settings = Settings()

    assert settings.smtp_require_delivery_value
