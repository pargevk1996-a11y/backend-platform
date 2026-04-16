from __future__ import annotations

import pytest
from app.core.config import Settings
from cryptography.fernet import Fernet
from pydantic import ValidationError

PRIVATE_KEY_STUB = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
PUBLIC_KEY_STUB = "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"


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

    settings = Settings()

    assert settings.smtp_from_email_value == "mailer@example.com"
    assert settings.smtp_is_configured


def test_development_requires_delivery_when_smtp_is_partially_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    settings = Settings()

    assert settings.smtp_require_delivery_value


def test_api_docs_are_disabled_outside_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_required_env(monkeypatch)

    assert Settings().api_docs_enabled

    monkeypatch.setenv("SERVICE_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("JWT_PRIVATE_KEY", PRIVATE_KEY_STUB)
    monkeypatch.setenv("JWT_PUBLIC_KEY", PUBLIC_KEY_STUB)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.com")

    assert not Settings().api_docs_enabled
