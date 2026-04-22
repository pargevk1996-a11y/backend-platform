"""Browser-oriented BFF endpoints: store refresh tokens in HttpOnly cookies, not JSON.

Machine/API clients should continue to call ``/v1/auth/*`` and ``/v1/tokens/*`` and handle
Bearer + refresh in the response body.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.deps import get_rate_limiter, get_routing_service, get_settings_dep
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.core.security import get_client_ip
from app.services.routing_service import RoutingService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/browser-auth", tags=["browser-auth"])

_UPSTREAM = {
    "register": "/v1/auth/register",
    "login": "/v1/auth/login",
    "login_2fa": "/v1/auth/login/2fa",
    "refresh": "/v1/tokens/refresh",
    "revoke": "/v1/tokens/revoke",
}


def _strip_refresh_from_json(data: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Remove refresh material from JSON and return the raw refresh string if present."""
    refresh: str | None = None
    out = dict(data)
    if "tokens" in out and isinstance(out["tokens"], dict):
        nested = dict(out["tokens"])
        rt = nested.get("refresh_token")
        if isinstance(rt, str):
            refresh = rt
            nested.pop("refresh_token", None)
            out["tokens"] = nested
    rt_top = out.get("refresh_token")
    if isinstance(rt_top, str):
        refresh = rt_top
        out.pop("refresh_token", None)
    return out, refresh


def _set_refresh_cookie(response: Response, *, settings: Settings, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_cookie_max_age_seconds,
        path="/",
        httponly=True,
        secure=settings.is_refresh_cookie_secure,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name,
        path="/",
        samesite="lax",
        secure=settings.is_refresh_cookie_secure,
    )


async def _forward_json(
    *,
    request: Request,
    upstream_path: str,
    body: bytes,
    settings: Settings,
    rate_limiter: RateLimiter,
    routing_service: RoutingService,
    set_cookie_on_ok: bool,
    clear_cookie_on_ok: bool,
) -> Response:
    await rate_limiter.check(
        request=request,
        scope="public_auth",
        limit_per_minute=settings.rate_limit_public_auth_per_minute,
    )
    client_ip = get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips)
    headers = dict(request.headers)
    proxied = await routing_service.forward(
        method="POST",
        path=upstream_path,
        params=httpx.QueryParams(),
        headers=headers,
        body=body,
        client_ip=client_ip,
    )

    ct = proxied.headers.get("content-type", "").lower()
    if proxied.status_code < 400 and "application/json" in ct:
        try:
            parsed = json.loads(proxied.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response(
                content=proxied.body,
                status_code=proxied.status_code,
                headers=dict(proxied.headers),
            )
        if not isinstance(parsed, dict):
            return Response(
                content=proxied.body,
                status_code=proxied.status_code,
                headers=dict(proxied.headers),
            )

        out_json = parsed
        refresh_val: str | None = None
        if set_cookie_on_ok:
            out_json, refresh_val = _strip_refresh_from_json(parsed)

        response = Response(
            content=json.dumps(out_json).encode("utf-8"),
            status_code=proxied.status_code,
            media_type="application/json",
        )
        if set_cookie_on_ok and refresh_val:
            _set_refresh_cookie(response, settings=settings, refresh_token=refresh_val)
        if clear_cookie_on_ok and proxied.status_code < 400:
            _clear_refresh_cookie(response, settings=settings)
        return response

    return Response(
        content=proxied.body,
        status_code=proxied.status_code,
        headers=dict(proxied.headers),
    )


@router.post("/register")
async def browser_register(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    body = await request.body()
    return await _forward_json(
        request=request,
        upstream_path=_UPSTREAM["register"],
        body=body,
        settings=settings,
        rate_limiter=rate_limiter,
        routing_service=routing_service,
        set_cookie_on_ok=False,
        clear_cookie_on_ok=False,
    )


@router.post("/login")
async def browser_login(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    body = await request.body()
    return await _forward_json(
        request=request,
        upstream_path=_UPSTREAM["login"],
        body=body,
        settings=settings,
        rate_limiter=rate_limiter,
        routing_service=routing_service,
        set_cookie_on_ok=True,
        clear_cookie_on_ok=False,
    )


@router.post("/login/2fa")
async def browser_login_2fa(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    body = await request.body()
    return await _forward_json(
        request=request,
        upstream_path=_UPSTREAM["login_2fa"],
        body=body,
        settings=settings,
        rate_limiter=rate_limiter,
        routing_service=routing_service,
        set_cookie_on_ok=True,
        clear_cookie_on_ok=False,
    )


@router.post("/refresh")
async def browser_refresh(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    refresh_from_cookie = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_from_cookie:
        rid = getattr(request.state, "request_id", None)
        LOGGER.info(
            "browser_auth_missing_refresh_cookie",
            extra={
                "request_id": rid,
                "endpoint": "browser_refresh",
                "cookie_name": settings.refresh_cookie_name,
            },
        )
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "HTTP_ERROR",
                "message": "Missing refresh cookie",
                "request_id": rid,
            },
        )
    body = json.dumps({"refresh_token": refresh_from_cookie}).encode("utf-8")
    return await _forward_json(
        request=request,
        upstream_path=_UPSTREAM["refresh"],
        body=body,
        settings=settings,
        rate_limiter=rate_limiter,
        routing_service=routing_service,
        set_cookie_on_ok=True,
        clear_cookie_on_ok=False,
    )


@router.post("/revoke")
async def browser_revoke(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    refresh_from_cookie = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_from_cookie:
        rid = getattr(request.state, "request_id", None)
        LOGGER.info(
            "browser_auth_missing_refresh_cookie",
            extra={
                "request_id": rid,
                "endpoint": "browser_revoke",
                "cookie_name": settings.refresh_cookie_name,
            },
        )
        return JSONResponse(
            status_code=401,
            content={
                "error_code": "HTTP_ERROR",
                "message": "Missing refresh cookie",
                "request_id": rid,
            },
        )
    raw_body = await request.body()
    revoke_family = True
    if raw_body:
        try:
            extra = json.loads(raw_body.decode("utf-8") or "{}")
            if isinstance(extra, dict) and "revoke_family" in extra:
                revoke_family = bool(extra["revoke_family"])
        except json.JSONDecodeError:
            pass
    body = json.dumps(
        {"refresh_token": refresh_from_cookie, "revoke_family": revoke_family}
    ).encode("utf-8")
    return await _forward_json(
        request=request,
        upstream_path=_UPSTREAM["revoke"],
        body=body,
        settings=settings,
        rate_limiter=rate_limiter,
        routing_service=routing_service,
        set_cookie_on_ok=False,
        clear_cookie_on_ok=True,
    )
