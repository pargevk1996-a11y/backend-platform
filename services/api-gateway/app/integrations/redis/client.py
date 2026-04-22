from __future__ import annotations

from typing import cast

from fastapi import Request
from redis.asyncio import Redis


async def create_redis_client(redis_url: str) -> Redis:
    return cast(Redis, Redis.from_url(redis_url, encoding="utf-8", decode_responses=True))


async def close_redis_client(redis: Redis) -> None:
    await redis.close()


async def get_redis(request: Request) -> Redis:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RuntimeError("Redis client is not initialized")
    return cast(Redis, redis)
