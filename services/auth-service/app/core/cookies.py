from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Response

from app.core.config import Settings


def build_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    now = datetime.now(tz=UTC)
    access_exp = now + timedelta(seconds=settings.jwt_access_ttl_seconds)
    refresh_exp = now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)

    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
        expires=access_exp,
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
        expires=refresh_exp,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
        expires=refresh_exp,
    )


def clear_auth_cookies(response: Response, *, settings: Settings) -> None:
    for key in (
        settings.access_cookie_name,
        settings.refresh_cookie_name,
        settings.csrf_cookie_name,
    ):
        response.delete_cookie(
            key=key,
            path="/",
            domain=settings.cookie_domain,
        )
