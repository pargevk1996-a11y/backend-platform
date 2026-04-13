from __future__ import annotations

from functools import lru_cache

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.rate_limit import RateLimiter
from app.core.security import AccessTokenService
from app.integrations.redis.client import get_redis
from app.services.routing_service import RoutingService


@lru_cache(maxsize=1)
def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache(maxsize=1)
def get_access_token_service() -> AccessTokenService:
    return AccessTokenService(get_settings())


async def get_rate_limiter(request: Request) -> RateLimiter:
    redis: Redis = await get_redis(request)
    return RateLimiter(redis=redis, settings=get_settings())


async def get_routing_service(request: Request) -> RoutingService:
    routing_service = getattr(request.app.state, "routing_service", None)
    if routing_service is None:
        raise RuntimeError("Routing service is not initialized")
    return routing_service
