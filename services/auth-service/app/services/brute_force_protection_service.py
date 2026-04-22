from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.privacy import stable_hmac_digest
from app.exceptions.auth import AccountLockedException
from app.integrations.redis.keys import brute_force_fail_key, brute_force_lock_key


@dataclass(slots=True)
class BruteForcePolicy:
    max_attempts: int
    window_seconds: int
    lock_seconds: int


class BruteForceProtectionService:
    """Redis-backed anti-bruteforce guard for login and 2FA endpoints."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    def _identifier_digest(self, identifier: str) -> str:
        return stable_hmac_digest(
            value=identifier,
            pepper=self.settings.privacy_key_pepper_value,
        )

    def _policy(self, scope: str) -> BruteForcePolicy:
        if scope in {"login", "login_account"}:
            return BruteForcePolicy(
                max_attempts=self.settings.brute_force_login_max_attempts,
                window_seconds=self.settings.brute_force_login_window_seconds,
                lock_seconds=self.settings.brute_force_login_lock_seconds,
            )
        if scope == "2fa":
            return BruteForcePolicy(
                max_attempts=self.settings.brute_force_2fa_max_attempts,
                window_seconds=self.settings.brute_force_2fa_window_seconds,
                lock_seconds=self.settings.brute_force_2fa_lock_seconds,
            )
        if scope in {"password_reset", "password_reset_account"}:
            return BruteForcePolicy(
                max_attempts=self.settings.brute_force_password_reset_max_attempts,
                window_seconds=self.settings.brute_force_password_reset_window_seconds,
                lock_seconds=self.settings.brute_force_password_reset_lock_seconds,
            )
        raise ValueError(f"Unsupported brute-force scope: {scope}")

    async def assert_not_locked(self, *, scope: str, identifier: str) -> None:
        lock_key = brute_force_lock_key(scope=scope, identifier=self._identifier_digest(identifier))
        is_locked = await self.redis.exists(lock_key)
        if is_locked:
            ttl = await self.redis.ttl(lock_key)
            raise AccountLockedException(
                f"Too many failed attempts. Retry in {max(ttl, 1)} seconds"
            )

    async def record_failure(self, *, scope: str, identifier: str) -> int:
        policy = self._policy(scope)
        key_identifier = self._identifier_digest(identifier)
        fail_key = brute_force_fail_key(scope=scope, identifier=key_identifier)
        lock_key = brute_force_lock_key(scope=scope, identifier=key_identifier)

        attempts = await self.redis.incr(fail_key)
        if attempts == 1:
            await self.redis.expire(fail_key, policy.window_seconds)

        if attempts >= policy.max_attempts:
            await self.redis.set(lock_key, "1", ex=policy.lock_seconds)
            await self.redis.delete(fail_key)

        return attempts

    async def clear_failures(self, *, scope: str, identifier: str) -> None:
        key_identifier = self._identifier_digest(identifier)
        fail_key = brute_force_fail_key(scope=scope, identifier=key_identifier)
        lock_key = brute_force_lock_key(scope=scope, identifier=key_identifier)
        await self.redis.delete(fail_key, lock_key)
