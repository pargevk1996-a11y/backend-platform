from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import (
    get_access_token_service,
    get_rate_limiter,
    get_routing_service,
    get_settings_dep,
)
from app.core.config import Settings
from app.core.cookies import (
    access_cookie,
    clear_browser_auth_cookies,
    encode_json_body,
    extract_token_pair,
    read_json_body,
    refresh_cookie,
    require_cookie_csrf_for_unsafe,
    require_csrf,
    sanitized_auth_payload,
    set_browser_auth_cookies,
)
from app.core.rate_limit import RateLimiter
from app.core.security import (
    AccessTokenService,
    ensure_access_session_active,
    extract_bearer_token,
    get_client_ip,
    is_public_endpoint,
)
from app.exceptions.gateway import UnauthorizedException
from app.services.routing_service import RoutingService

router = APIRouter(tags=["proxy"])

TOKEN_ISSUING_PATHS = {
    "/v1/auth/register",
    "/v1/auth/login",
    "/v1/auth/login/2fa",
    "/v1/tokens/refresh",
}


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

    headers = dict(request.headers)
    body = await request.body()
    client_ip = get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips)
    if is_public:
        await rate_limiter.check(
            request=request,
            scope="public_auth",
            limit_per_minute=settings.rate_limit_public_auth_per_minute,
        )
        if path in {"/v1/tokens/refresh", "/v1/tokens/revoke"}:
            parsed_body = read_json_body(body)
            refresh_token = parsed_body.get("refresh_token") if parsed_body is not None else None
            browser_refresh = refresh_cookie(request, settings)
            if not refresh_token and browser_refresh:
                require_csrf(request, settings)
                payload = parsed_body or {}
                payload["refresh_token"] = browser_refresh
                if path == "/v1/tokens/revoke":
                    payload.setdefault("revoke_family", True)
                body = encode_json_body(payload)
                headers["Content-Type"] = "application/json"
            elif path == "/v1/tokens/revoke" and not refresh_token and not browser_refresh:
                response = Response(
                    content=encode_json_body({"message": "No active browser session"}),
                    status_code=200,
                    media_type="application/json",
                )
                clear_browser_auth_cookies(response, settings=settings)
                return response
    else:
        await rate_limiter.check(
            request=request,
            scope="protected",
            limit_per_minute=settings.rate_limit_protected_per_minute,
        )
        used_cookie_auth = False
        try:
            token = extract_bearer_token(request, settings=settings)
        except UnauthorizedException:
            cookie_token = access_cookie(request, settings)
            if not cookie_token:
                raise
            token = cookie_token
            used_cookie_auth = True
        require_cookie_csrf_for_unsafe(
            request,
            settings=settings,
            method=method,
            used_cookie_auth=used_cookie_auth,
        )
        claims = access_token_service.decode_access_token(token)
        await ensure_access_session_active(rate_limiter.redis, claims.sid)
        await routing_service.auth_client.touch_session(access_token=token)
        headers["Authorization"] = f"Bearer {token}"

    query_params = httpx.QueryParams(tuple(request.query_params.multi_items()))
    proxied = await routing_service.forward(
        method=method,
        path=path,
        params=query_params,
        headers=headers,
        body=body,
        client_ip=client_ip,
    )

    response_body = proxied.body
    response_headers = dict(proxied.headers)
    response = Response(
        content=response_body,
        status_code=proxied.status_code,
        headers=response_headers,
    )

    if proxied.status_code in {200, 201} and path in TOKEN_ISSUING_PATHS:
        parsed = read_json_body(proxied.body)
        if parsed is not None:
            token_pair = extract_token_pair(parsed)
            if token_pair is not None:
                response_body = encode_json_body(
                    sanitized_auth_payload(path=path, original=parsed, token_pair=token_pair)
                )
                response_headers["content-type"] = "application/json"
                response = Response(
                    content=response_body,
                    status_code=proxied.status_code,
                    headers=response_headers,
                )
                set_browser_auth_cookies(response, settings=settings, token_pair=token_pair)

    if proxied.status_code < 400 and path == "/v1/tokens/revoke":
        clear_browser_auth_cookies(response, settings=settings)
    elif proxied.status_code in {401, 403} and path == "/v1/tokens/refresh":
        clear_browser_auth_cookies(response, settings=settings)

    return response
