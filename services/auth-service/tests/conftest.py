from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _configure_test_env() -> None:
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://auth:auth@localhost:5432/auth"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_PRIVATE_KEY"] = "test-jwt-signing-secret"
    os.environ["JWT_PUBLIC_KEY"] = "test-jwt-signing-secret"
    os.environ["REFRESH_TOKEN_HASH_PEPPER"] = "test-refresh-pepper-very-long-secret-value"
    os.environ["PRIVACY_KEY_PEPPER"] = "test-privacy-pepper-very-long-secret-value"
    os.environ["TOTP_ENCRYPTION_KEY"] = Fernet.generate_key().decode("utf-8")

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
