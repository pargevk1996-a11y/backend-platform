from __future__ import annotations

import pytest
from app.core.config import Settings

PUBLIC_KEY_STUB = "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"


def test_production_rejects_symmetric_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    with pytest.raises(ValueError, match="asymmetric JWT"):
        Settings()  # type: ignore[call-arg]


def test_production_rejects_wildcard_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("JWT_ALGORITHM", "RS256")
    monkeypatch.setenv("JWT_PUBLIC_KEY", PUBLIC_KEY_STUB)

    with pytest.raises(ValueError, match="Wildcard CORS"):
        Settings()  # type: ignore[call-arg]
