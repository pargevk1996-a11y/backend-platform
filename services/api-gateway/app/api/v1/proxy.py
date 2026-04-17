from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import (
    get_access_token_service,
    get_rate_limiter,
    get_routing_service,
    get_settings_dep,
)
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.core.security import (
    AccessTokenService,
    apply_token_cookies,
    clear_token_cookies,
    ensure_access_session_active,
    extract_access_token,
    extract_refresh_token,
    get_client_ip,
    is_public_endpoint,
    is_session_endpoint,
    issue_csrf_token,
)
from app.services.routing_service import RoutingService

router = APIRouter(tags=["proxy"])

TOKEN_ISSUING_ENDPOINTS = {
    ("POST", "/v1/auth/register"),
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/auth/login/2fa"),
    ("POST", "/v1/tokens/refresh"),
}


def _load_json_body(body: bytes) -> dict[str, object] | None:
    if not body:
        return {}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _inject_refresh_token_body(
    *,
    body: bytes,
    request: Request,
    settings: Settings,
) -> bytes:
    payload = _load_json_body(body)
    if payload is None:
        return body
    if isinstance(payload.get("refresh_token"), str) and payload["refresh_token"].strip():
        return json.dumps(payload).encode("utf-8")

    payload["refresh_token"] = extract_refresh_token(request, settings=settings)
    return json.dumps(payload).encode("utf-8")


def _extract_tokens_from_payload(
    *,
    method: str,
    path: str,
    payload: dict[str, object],
) -> dict[str, object] | None:
    if (method, path) not in TOKEN_ISSUING_ENDPOINTS:
        return None

    if (method, path) == ("POST", "/v1/auth/login"):
        tokens = payload.get("tokens")
        if isinstance(tokens, dict):
            return tokens
        return None

    return payload


def _sanitize_auth_payload(
    *,
    method: str,
    path: str,
    payload: dict[str, object],
    token_payload: dict[str, object] | None,
) -> dict[str, object]:
    if token_payload is None:
        return payload

    sanitized = dict(payload)
    sanitized.pop("access_token", None)
    sanitized.pop("refresh_token", None)
    sanitized["authenticated"] = True

    if (method, path) == ("POST", "/v1/auth/login"):
        sanitized.pop("tokens", None)
        sanitized["requires_2fa"] = False
    else:
        sanitized["token_type"] = token_payload.get("token_type", "Bearer")
    sanitized["expires_in"] = token_payload.get("expires_in")
    return sanitized


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_request(
    full_path: str,
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    access_token_service: AccessTokenService = Depends(get_access_token_service),
    routing_service: RoutingService = Depends(get_routing_service),
) -> Response:
    path = "/" + full_path.lstrip("/")
    if not path.startswith("/v1/"):
        path = f"/v1/{path.lstrip('/')}"

    method = request.method.upper()
    is_public = is_public_endpoint(method, path)
    is_session = is_session_endpoint(method, path)

    body = await request.body()
    headers = dict(request.headers)
    client_ip = get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips)
    if is_public:
        await rate_limiter.check(
            request=request,
            scope="public_auth",
            limit_per_minute=settings.rate_limit_public_auth_per_minute,
        )
    elif is_session:
        await rate_limiter.check(
            request=request,
            scope="public_auth",
            limit_per_minute=settings.rate_limit_public_auth_per_minute,
        )
        body = _inject_refresh_token_body(body=body, request=request, settings=settings)
    else:
        await rate_limiter.check(
            request=request,
            scope="protected",
            limit_per_minute=settings.rate_limit_protected_per_minute,
        )
        token = extract_access_token(request, settings=settings)
        headers["Authorization"] = f"Bearer {token}"
        claims = access_token_service.decode_access_token(token)
        await ensure_access_session_active(rate_limiter.redis, claims.sid)
        await routing_service.auth_client.touch_session(access_token=token)

    query_params = httpx.QueryParams(tuple(request.query_params.multi_items()))
    proxied = await routing_service.forward(
        method=method,
        path=path,
        params=query_params,
        headers=headers,
        body=body,
        client_ip=client_ip,
    )
    response_headers = dict(proxied.headers)
    response_headers["Cache-Control"] = "no-store"

    payload = _load_json_body(proxied.body)
    token_payload = (
        _extract_tokens_from_payload(method=method, path=path, payload=payload)
        if payload is not None
        else None
    )

    response_body = proxied.body
    if payload is not None:
        sanitized_payload = _sanitize_auth_payload(
            method=method,
            path=path,
            payload=payload,
            token_payload=token_payload,
        )
        response_body = json.dumps(sanitized_payload).encode("utf-8")

    response = Response(
        content=response_body,
        status_code=proxied.status_code,
        headers=response_headers,
    )

    if proxied.status_code < 400 and token_payload is not None:
        access_token = token_payload.get("access_token")
        refresh_token = token_payload.get("refresh_token")
        expires_in = token_payload.get("expires_in")
        if (
            isinstance(access_token, str)
            and isinstance(refresh_token, str)
            and isinstance(expires_in, int)
        ):
            apply_token_cookies(
                response,
                settings=settings,
                access_token=access_token,
                refresh_token=refresh_token,
                access_ttl_seconds=expires_in,
                csrf_token=issue_csrf_token(),
            )

    if (method, path) == ("POST", "/v1/tokens/revoke") and proxied.status_code < 400:
        clear_token_cookies(response, settings=settings)

    if is_session and proxied.status_code in {401, 403}:
        clear_token_cookies(response, settings=settings)

    return response
