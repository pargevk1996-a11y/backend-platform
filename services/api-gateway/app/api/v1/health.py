from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.schemas.common import HealthResponse

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="redis_not_initialized")
    await redis.ping()

    http_client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if http_client is None:
        raise HTTPException(status_code=503, detail="http_client_not_initialized")

    settings = request.app.state.settings
    # Internal service URLs must not leak into public health payloads. Failing
    # upstreams are logged server-side with the URL, but the HTTP response
    # surfaces only a stable machine-readable code.
    upstreams = (
        ("auth", settings.auth_service_url),
        ("user", settings.user_service_url),
    )
    for name, service_url in upstreams:
        try:
            response = await http_client.get(f"{service_url.rstrip('/')}/v1/health/ready")
            if response.status_code >= 500:
                LOGGER.warning(
                    "gateway.readiness.upstream_unavailable",
                    extra={"upstream": name, "url": service_url, "status": response.status_code},
                )
                raise HTTPException(status_code=503, detail=f"upstream_unavailable:{name}")
        except httpx.HTTPError as exc:
            LOGGER.warning(
                "gateway.readiness.upstream_error",
                extra={"upstream": name, "url": service_url, "error": str(exc)},
            )
            raise HTTPException(
                status_code=503, detail=f"upstream_unavailable:{name}"
            ) from exc

    return HealthResponse(status="ok")
