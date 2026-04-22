from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not initialized")
    await redis.ping()

    http_client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)
    if http_client is None:
        raise HTTPException(status_code=503, detail="HTTP client is not initialized")

    settings = request.app.state.settings
    for service_url in (settings.auth_service_url, settings.user_service_url):
        try:
            response = await http_client.get(f"{service_url.rstrip('/')}/v1/health/live")
            if response.status_code >= 500:
                raise HTTPException(status_code=503, detail=f"Upstream {service_url} unavailable")
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503, detail=f"Upstream {service_url} unavailable"
            ) from exc

    return HealthResponse(status="ok")
