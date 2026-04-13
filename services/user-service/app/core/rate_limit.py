from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.privacy import stable_hmac_digest
from app.exceptions.auth import TooManyRequestsException
from app.integrations.redis.client import get_redis
from app.integrations.redis.keys import rate_limit_key
from app.core.security import get_client_ip


async def _apply_rate_limit(*, redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > limit:
        raise TooManyRequestsException("Rate limit exceeded")


def rate_limit_dependency(scope: str, limit_per_minute: int) -> Callable[..., object]:
    async def _dependency(
        request: Request,
        redis: Redis = Depends(get_redis),
        settings: Settings = Depends(get_settings),
    ) -> None:
        ip = get_client_ip(request)
        client_hash = stable_hmac_digest(value=ip, pepper=settings.privacy_key_pepper_value)
        bucket = int(time.time() // 60)
        key = rate_limit_key(scope=scope, ip=client_hash, bucket=bucket)
        await _apply_rate_limit(redis=redis, key=key, limit=limit_per_minute, window_seconds=61)

    return _dependency
