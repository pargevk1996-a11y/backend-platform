from __future__ import annotations

import time

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.privacy import stable_hmac_digest
from app.exceptions.gateway import TooManyRequestsException
from app.integrations.redis.keys import rate_limit_key
from app.core.security import get_client_ip


class RateLimiter:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    async def check(self, *, request: Request, scope: str, limit_per_minute: int) -> None:
        ip = get_client_ip(request)
        client_hash = stable_hmac_digest(value=ip, pepper=self.settings.privacy_key_pepper_value)
        bucket = int(time.time() // 60)
        key = rate_limit_key(scope=scope, ip=client_hash, bucket=bucket)

        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, 61)

        if current > limit_per_minute:
            raise TooManyRequestsException("Rate limit exceeded")
