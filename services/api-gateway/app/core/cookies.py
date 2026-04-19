from __future__ import annotations

import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response

from app.core.config import Settings
from app.exceptions.gateway import ForbiddenException

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-csrf-token"


@dataclass(slots=True, frozen=True)
class BrowserTokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def read_json_body(body: bytes) -> dict[str, Any] | None:
    if not body:
        return {}
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def encode_json_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def access_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.auth_access_cookie_name)


def refresh_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.auth_refresh_cookie_name)


def csrf_cookie(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.auth_csrf_cookie_name)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def require_csrf(request: Request, settings: Settings) -> None:
    expected = csrf_cookie(request, settings)
    actual = request.headers.get(CSRF_HEADER)
    if not expected or not actual or not hmac.compare_digest(expected, actual):
        raise ForbiddenException("Missing or invalid CSRF token")


def require_cookie_csrf_for_unsafe(
    request: Request,
    *,
    settings: Settings,
    method: str,
    used_cookie_auth: bool,
) -> None:
    if used_cookie_auth and method.upper() in UNSAFE_METHODS:
        require_csrf(request, settings)


def extract_token_pair(payload: dict[str, Any]) -> BrowserTokenPair | None:
    source: dict[str, Any] | None = None
    if "access_token" in payload or "refresh_token" in payload:
        source = payload
    elif isinstance(payload.get("tokens"), dict):
        source = payload["tokens"]

    if source is None:
        return None

    access_token = source.get("access_token")
    refresh_token = source.get("refresh_token")
    expires_in = source.get("expires_in")
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        return None
    if not isinstance(expires_in, int):
        expires_in = settings_access_cookie_default()
    return BrowserTokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


def settings_access_cookie_default() -> int:
    return 900


def _cookie_domain(settings: Settings) -> str | None:
    # Starlette rejects an empty-string domain; only forward non-empty values.
    domain = settings.auth_cookie_domain
    return domain if domain else None


def set_browser_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    token_pair: BrowserTokenPair,
) -> None:
    csrf_token = new_csrf_token()
    secure = settings.auth_cookie_secure_value
    same_site = settings.auth_cookie_samesite
    domain = _cookie_domain(settings)
    # Hard cap access cookie lifetime. expires_in is trusted input from the
    # auth-service upstream, so clamp it regardless of what was returned.
    access_max_age = min(
        max(int(token_pair.expires_in), 0),
        settings.auth_access_cookie_max_age_seconds,
    )
    response.set_cookie(
        settings.auth_access_cookie_name,
        token_pair.access_token,
        max_age=access_max_age,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )
    response.set_cookie(
        settings.auth_refresh_cookie_name,
        token_pair.refresh_token,
        max_age=settings.auth_refresh_cookie_max_age_seconds,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )
    response.set_cookie(
        settings.auth_csrf_cookie_name,
        csrf_token,
        max_age=settings.auth_refresh_cookie_max_age_seconds,
        httponly=False,
        secure=secure,
        samesite=same_site,
        domain=domain,
        path="/",
    )


def clear_browser_auth_cookies(response: Response, *, settings: Settings) -> None:
    domain = _cookie_domain(settings)
    for name in (
        settings.auth_access_cookie_name,
        settings.auth_refresh_cookie_name,
        settings.auth_csrf_cookie_name,
    ):
        response.delete_cookie(
            name,
            path="/",
            domain=domain,
            secure=settings.auth_cookie_secure_value,
            samesite=settings.auth_cookie_samesite,
        )


def sanitized_auth_payload(
    *,
    path: str,
    original: dict[str, Any],
    token_pair: BrowserTokenPair,
) -> dict[str, Any]:
    if path == "/v1/auth/login":
        return {
            "requires_2fa": False,
            "status": "authenticated",
            "auth": "cookie",
            "expires_in": token_pair.expires_in,
        }
    if path == "/v1/tokens/refresh":
        return {
            "status": "refreshed",
            "auth": "cookie",
            "expires_in": token_pair.expires_in,
        }
    if original.get("requires_2fa") is True:
        return {"requires_2fa": True, "challenge_id": original.get("challenge_id")}
    return {
        "status": "authenticated",
        "auth": "cookie",
        "expires_in": token_pair.expires_in,
    }
