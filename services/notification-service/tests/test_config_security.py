from __future__ import annotations

import pytest
from app.core.config import Settings


def test_api_docs_are_disabled_outside_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERVICE_ENV", "development")

    assert Settings().api_docs_enabled

    monkeypatch.setenv("SERVICE_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com")

    assert not Settings().api_docs_enabled
