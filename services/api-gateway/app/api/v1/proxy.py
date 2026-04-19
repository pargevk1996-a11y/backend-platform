from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

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
from app.exceptions.gateway import UnauthorizedException, UpstreamServiceException
from app.services.routing_service import RoutingService

LOGGER = logging.getLogger(__name__)

router = APIRouter(tags=["proxy"])

TOKEN_ISSUING_PATHS = {
    "/v1/auth/register",
    "/v1/auth/login",
    "/v1/auth/login/2fa",
    "/v1/tokens/refresh",
}

# Maximum raw body accepted for proxied API calls. Nginx caps inbound size
# with client_max_body_size, but the gateway enforces its own limit so it is
# safe when run bare (tests, local dev without nginx).
MAX_PROXY_BODY_BYTES = 2 * 1024 * 1024

# Touch the auth-service session once per interval per sid to avoid amplifying
# every protected request into an extra upstream round-trip.
SESSION_TOUCH_DEBOUNCE_SECONDS = 60


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

    # Envelope limit applied before any per-scope bucket. A single misbehaving
    # client cannot exhaust multiple scope quotas by rotating endpoints.
    await rate_limiter.check(
        request=request,
        scope="global",
        limit_per_minute=settings.rate_limit_global_per_minute,
    )

    headers = dict(request.headers)

    declared_length = headers.get("content-length")
    if (
        declared_length
        and declared_length.isdigit()
        and int(declared_length) > MAX_PROXY_BODY_BYTES
    ):
        raise HTTPException(status_code=413, detail="Payload too large")

    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_PROXY_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")
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
        # Debounce session touches so bursty protected requests do not generate
        # one upstream round-trip per request. Redis SET NX acts as a
        # distributed lease across gateway replicas.
        touch_key = f"bp:gw:touch:{claims.sid}"
        should_touch = await rate_limiter.redis.set(
            touch_key, "1", nx=True, ex=SESSION_TOUCH_DEBOUNCE_SECONDS
        )
        if should_touch:
            try:
                await routing_service.auth_client.touch_session(access_token=token)
            except UpstreamServiceException:
                LOGGER.warning(
                    "gateway.touch_session_failed",
                    extra={"sid": str(claims.sid)},
                )
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
                # Starlette recomputes Content-Length from body, so strip any
                # stale framing headers that came from the upstream response.
                for stale in ("content-length", "content-encoding", "transfer-encoding"):
                    response_headers.pop(stale, None)
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
