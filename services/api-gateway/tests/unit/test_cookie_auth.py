from __future__ import annotations

from app.core.config import get_settings
from app.core.cookies import (
    BrowserTokenPair,
    extract_token_pair,
    sanitized_auth_payload,
    set_browser_auth_cookies,
)
from fastapi import Response


def test_browser_auth_payload_strips_tokens() -> None:
    payload = {
        "requires_2fa": False,
        "tokens": {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 900,
        },
    }

    token_pair = extract_token_pair(payload)
    assert token_pair is not None

    sanitized = sanitized_auth_payload(
        path="/v1/auth/login",
        original=payload,
        token_pair=token_pair,
    )

    assert sanitized == {
        "requires_2fa": False,
        "status": "authenticated",
        "auth": "cookie",
        "expires_in": 900,
    }
    assert "tokens" not in sanitized
    assert "access_token" not in sanitized
    assert "refresh_token" not in sanitized


def test_browser_auth_cookies_are_httponly_for_tokens() -> None:
    settings = get_settings()
    response = Response()

    set_browser_auth_cookies(
        response,
        settings=settings,
        token_pair=BrowserTokenPair(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=900,
        ),
    )

    set_cookie_headers = [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.decode("latin-1").lower() == "set-cookie"
    ]

    access_cookie = next(
        header for header in set_cookie_headers if header.startswith("bp_access_token=")
    )
    refresh_cookie = next(
        header for header in set_cookie_headers if header.startswith("bp_refresh_token=")
    )
    csrf_cookie = next(
        header for header in set_cookie_headers if header.startswith("bp_csrf_token=")
    )

    assert "HttpOnly" in access_cookie
    assert "HttpOnly" in refresh_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in access_cookie
