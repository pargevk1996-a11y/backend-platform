from __future__ import annotations

import pytest
from starlette.requests import Request

from app.core.config import get_settings
from app.core.security import effective_refresh_cookie_secure


def _request(
    *,
    scheme: str = "http",
    client: tuple[str, int] = ("198.18.0.99", 12345),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "path": "/v1/browser-auth/login",
            "raw_path": b"/v1/browser-auth/login",
            "root_path": "",
            "scheme": scheme,
            "query_string": b"",
            "headers": headers or [],
            "client": client,
            "server": ("testserver", 80),
        }
    )


def test_auto_secure_direct_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_COOKIE_SECURE", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(scheme="https")
    assert effective_refresh_cookie_secure(req, settings) is True
    get_settings.cache_clear()


def test_auto_insecure_plain_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_COOKIE_SECURE", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(scheme="http")
    assert effective_refresh_cookie_secure(req, settings) is False
    get_settings.cache_clear()


def test_auto_secure_forwarded_proto_from_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "198.18.0.99")
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(
        scheme="http",
        client=("198.18.0.99", 12345),
        headers=[
            (b"x-forwarded-for", b"203.0.113.50"),
            (b"x-forwarded-proto", b"https"),
        ],
    )
    assert effective_refresh_cookie_secure(req, settings) is True
    get_settings.cache_clear()


def test_forwarded_proto_ignored_without_forwarded_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """Proxies add XFF; trusting XFP alone breaks HTTP behind Docker (bridge in TRUSTED_PROXY_IPS)."""
    monkeypatch.delenv("REFRESH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "198.18.0.99")
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(
        scheme="http",
        client=("198.18.0.99", 12345),
        headers=[(b"x-forwarded-proto", b"https")],
    )
    assert effective_refresh_cookie_secure(req, settings) is False
    get_settings.cache_clear()


def test_forwarded_proto_ignored_from_untrusted_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("TRUSTED_PROXY_IPS", "198.18.0.1")
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(
        scheme="http",
        client=("198.18.0.99", 12345),
        headers=[(b"x-forwarded-proto", b"https")],
    )
    assert effective_refresh_cookie_secure(req, settings) is False
    get_settings.cache_clear()


def test_explicit_refresh_cookie_secure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFRESH_COOKIE_SECURE", "true")
    get_settings.cache_clear()
    settings = get_settings()
    req = _request(scheme="http")
    assert effective_refresh_cookie_secure(req, settings) is True
    get_settings.cache_clear()
