from __future__ import annotations

import logging
import time
from collections.abc import Callable

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.core.privacy import stable_hmac_digest
from app.core.security import get_client_ip
from app.exceptions.auth import ServiceUnavailableException, TooManyRequestsException
from app.integrations.redis.client import get_redis
from app.integrations.redis.keys import rate_limit_key

LOGGER = logging.getLogger(__name__)


async def _apply_rate_limit(*, redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
    except RedisError as exc:
        LOGGER.error("rate_limit.redis_error", extra={"error": str(exc)})
        raise ServiceUnavailableException("Rate limiter unavailable") from exc
    if current > limit:
        raise TooManyRequestsException("Rate limit exceeded")


def rate_limit_dependency(scope: str, limit_per_minute: int) -> Callable[..., object]:
    async def _dependency(
        request: Request,
        redis: Redis = Depends(get_redis),
        settings: Settings = Depends(get_settings),
    ) -> None:
        ip = get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips)
        client_hash = stable_hmac_digest(value=ip, pepper=settings.privacy_key_pepper_value)
        bucket = int(time.time() // 60)
        key = rate_limit_key(scope=scope, ip=client_hash, bucket=bucket)
        await _apply_rate_limit(redis=redis, key=key, limit=limit_per_minute, window_seconds=61)

    return _dependency
