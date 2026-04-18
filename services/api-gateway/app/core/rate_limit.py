from __future__ import annotations

import logging
import secrets
import time

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.privacy import stable_hmac_digest
from app.core.security import get_client_ip
from app.exceptions.gateway import ServiceUnavailableException, TooManyRequestsException
from app.integrations.redis.keys import rate_limit_key

LOGGER = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    async def check(self, *, request: Request, scope: str, limit_per_minute: int) -> None:
        ip = get_client_ip(request, trusted_proxy_ips=self.settings.trusted_proxy_ips)
        client_hash = stable_hmac_digest(value=ip, pepper=self.settings.privacy_key_pepper_value)
        key = rate_limit_key(scope=scope, ip=client_hash)
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - 60_000
        member = f"{now_ms}:{secrets.token_hex(4)}"

        try:
            pipeline = self.redis.pipeline(transaction=True)
            pipeline.zremrangebyscore(key, 0, window_start_ms)
            pipeline.zadd(key, {member: now_ms})
            pipeline.zcard(key)
            pipeline.expire(key, 61)
            _, _, current, _ = await pipeline.execute()
        except RedisError as exc:
            LOGGER.error("rate_limit.redis_error", extra={"error": str(exc), "scope": scope})
            raise ServiceUnavailableException("Rate limiter unavailable") from exc

        if current > limit_per_minute:
            raise TooManyRequestsException("Rate limit exceeded")
