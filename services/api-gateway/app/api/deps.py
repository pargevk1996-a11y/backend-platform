from __future__ import annotations

from functools import lru_cache
from typing import cast

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import AccessTokenService, extract_access_token
from app.integrations.redis.client import get_redis
from app.services.routing_service import RoutingService


@lru_cache(maxsize=1)
def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_access_token_service() -> AccessTokenService:
    return AccessTokenService(get_settings())


def get_request_access_token(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
) -> str:
    return extract_access_token(request, settings=settings)


async def get_rate_limiter(request: Request) -> RateLimiter:
    redis: Redis = await get_redis(request)
    return RateLimiter(redis=redis, settings=get_settings())


async def get_routing_service(request: Request) -> RoutingService:
    routing_service = getattr(request.app.state, "routing_service", None)
    if routing_service is None:
        raise RuntimeError("Routing service is not initialized")
    return cast(RoutingService, routing_service)
