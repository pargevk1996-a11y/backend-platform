"""SMTP username fallback for password reset delivery (Gmail-style env)."""

from __future__ import annotations

import pytest

from app.api.deps import get_email_provider
from app.core.config import get_settings


def test_get_email_provider_uses_from_email_when_smtp_username_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USERNAME", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "sixteen-char-appwd")
    get_settings.cache_clear()
    try:
        p = get_email_provider()
        assert p.username == "sender@gmail.com"
    finally:
        get_settings.cache_clear()
