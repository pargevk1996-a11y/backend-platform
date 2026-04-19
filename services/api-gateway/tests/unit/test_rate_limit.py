"""Cover the scope-based + global rate-limit primitives in the gateway."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.exceptions.gateway import TooManyRequestsException


class _InMemoryRedis:
    """Minimal Redis subset used by RateLimiter.check."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, ttl: int) -> None:  # pragma: no cover
        _ = (key, ttl)


def _fake_request(ip: str = "198.51.100.7") -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host=ip),
        headers={},
    )


@pytest.mark.asyncio
async def test_rate_limiter_allows_up_to_limit_then_raises() -> None:
    settings = get_settings()
    limiter = RateLimiter(redis=_InMemoryRedis(), settings=settings)

    limit = 5
    for _ in range(limit):
        await limiter.check(request=_fake_request(), scope="global", limit_per_minute=limit)

    with pytest.raises(TooManyRequestsException):
        await limiter.check(request=_fake_request(), scope="global", limit_per_minute=limit)


@pytest.mark.asyncio
async def test_rate_limiter_buckets_are_isolated_per_scope() -> None:
    settings = get_settings()
    limiter = RateLimiter(redis=_InMemoryRedis(), settings=settings)

    # 3 of 3 on scope A — next A-request would throttle.
    for _ in range(3):
        await limiter.check(request=_fake_request(), scope="a", limit_per_minute=3)

    # scope B with same IP is a clean bucket.
    await limiter.check(request=_fake_request(), scope="b", limit_per_minute=3)


@pytest.mark.asyncio
async def test_rate_limiter_buckets_are_isolated_per_ip() -> None:
    settings = get_settings()
    limiter = RateLimiter(redis=_InMemoryRedis(), settings=settings)

    for _ in range(3):
        await limiter.check(request=_fake_request("203.0.113.1"), scope="s", limit_per_minute=3)

    # Different client IP — fresh bucket even though scope matches.
    await limiter.check(request=_fake_request("203.0.113.2"), scope="s", limit_per_minute=3)


@pytest.mark.asyncio
async def test_global_scope_key_hashes_ip_to_avoid_raw_pii() -> None:
    """Key shape check: we never persist raw IP addresses in Redis."""
    redis = _InMemoryRedis()
    settings = get_settings()
    limiter = RateLimiter(redis=redis, settings=settings)

    await limiter.check(
        request=_fake_request("198.51.100.99"),
        scope="global",
        limit_per_minute=10,
    )

    assert len(redis._store) == 1
    key = next(iter(redis._store))
    assert key.startswith("rate_limit:global:")
    assert "198.51.100.99" not in key  # raw IP must never leak into keys
