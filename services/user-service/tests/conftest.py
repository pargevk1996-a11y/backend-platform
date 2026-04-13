from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _configure_test_env() -> None:
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:user@localhost:5432/user"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_PUBLIC_KEY"] = "user-service-test-key"
    os.environ["JWT_ISSUER"] = "backend-platform"
    os.environ["JWT_AUDIENCE"] = "backend-clients"
    os.environ["PRIVACY_KEY_PEPPER"] = "user-service-test-privacy-pepper-very-long"

    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
