from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.services.brute_force_protection_service import BruteForceProtectionService


class FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.values: dict[str, str] = {}
        self.seen_keys: list[str] = []

    async def exists(self, key: str) -> int:
        self.seen_keys.append(key)
        return int(key in self.values)

    async def ttl(self, key: str) -> int:
        _ = key
        return 1

    async def incr(self, key: str) -> int:
        self.seen_keys.append(key)
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        _ = (key, seconds)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        _ = ex
        self.seen_keys.append(key)
        self.values[key] = value

    async def delete(self, *keys: str) -> None:
        self.seen_keys.extend(keys)
        for key in keys:
            self.counters.pop(key, None)
            self.values.pop(key, None)


@pytest.mark.asyncio
async def test_bruteforce_uses_hashed_identifier_in_redis_keys() -> None:
    identifier = "user@example.com:127.0.0.1"
    account = "user@example.com"
    redis = FakeRedis()
    service = BruteForceProtectionService(redis=redis, settings=get_settings())

    await service.record_failure(scope="login", identifier=identifier)
    await service.record_failure(scope="login_account", identifier=account)
    await service.assert_not_locked(scope="login", identifier=identifier)
    await service.assert_not_locked(scope="login_account", identifier=account)

    assert redis.seen_keys
    assert all(identifier not in key for key in redis.seen_keys)
    assert all(account not in key for key in redis.seen_keys)
