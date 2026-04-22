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
from app.core.rate_limit import RateLimiter
from app.core.security import (
    AccessTokenService,
    ensure_access_session_active,
    extract_bearer_token,
    get_client_ip,
    is_public_endpoint,
)
from app.services.routing_service import RoutingService

router = APIRouter(tags=["proxy"])


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
    client_ip = get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips)
    if is_public:
        await rate_limiter.check(
            request=request,
            scope="public_auth",
            limit_per_minute=settings.rate_limit_public_auth_per_minute,
        )
    else:
        await rate_limiter.check(
            request=request,
            scope="protected",
            limit_per_minute=settings.rate_limit_protected_per_minute,
        )
        token = extract_bearer_token(request, settings=settings)
        claims = access_token_service.decode_access_token(token)
        await ensure_access_session_active(rate_limiter.redis, claims.sid)

    body = await request.body()
    query_params = httpx.QueryParams(tuple(request.query_params.multi_items()))
    proxied = await routing_service.forward(
        method=method,
        path=path,
        params=query_params,
        headers=headers,
        body=body,
        client_ip=client_ip,
    )

    return Response(
        content=proxied.body,
        status_code=proxied.status_code,
        headers=proxied.headers,
    )
