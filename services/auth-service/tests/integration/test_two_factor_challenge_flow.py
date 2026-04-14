from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.exceptions.two_factor import InvalidChallengeException
from app.services.auth_service import AuthService
from app.services.refresh_token_service import TokenPair


@dataclass
class FakeUser:
    id: UUID
    email: str
    password_hash: str
    two_factor_enabled: bool


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        _ = ex
        self.store[key] = value

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


class FakeUserRepository:
    def __init__(self, user: FakeUser) -> None:
        self.user = user

    async def get_by_email(self, session, email: str):
        _ = session
        return self.user if email == self.user.email else None

    async def get_by_id(self, session, user_id: UUID):
        _ = session
        return self.user if self.user.id == user_id else None


class FakePasswordService:
    def verify_password(self, password: str, password_hash: str) -> bool:
        return password == "CorrectPassword!1" and password_hash == "hash"


class FakeRefreshTokenService:
    async def issue_for_user(
        self, session, *, user_id: UUID, ip_address: str | None, user_agent: str | None
    ):
        _ = (session, user_id, ip_address, user_agent)
        return TokenPair(
            access_token="access",
            refresh_token="refresh",
            access_expires_in=900,
            refresh_family_id=uuid4(),
            session_id=uuid4(),
        )


class FakeTwoFactorService:
    async def verify_for_login(
        self, session, *, user, totp_code: str | None, backup_code: str | None
    ) -> None:
        _ = (session, user, backup_code)
        if totp_code != "123456":
            from app.exceptions.two_factor import InvalidTwoFactorCodeException

            raise InvalidTwoFactorCodeException()


class FakeBruteForceService:
    async def assert_not_locked(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)

    async def record_failure(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)

    async def clear_failures(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)


class FakeAuditService:
    async def log_event(self, session, **kwargs) -> None:
        _ = (session, kwargs)


@pytest.mark.asyncio
async def test_login_requires_2fa_and_challenge_verification_issues_tokens() -> None:
    user = FakeUser(
        id=uuid4(),
        email="user@example.com",
        password_hash="hash",
        two_factor_enabled=True,
    )
    session = FakeSession()
    redis = FakeRedis()

    service = AuthService(
        settings=get_settings(),
        redis=redis,
        user_repository=FakeUserRepository(user),
        password_service=FakePasswordService(),
        refresh_token_service=FakeRefreshTokenService(),
        two_factor_service=FakeTwoFactorService(),
        brute_force_service=FakeBruteForceService(),
        audit_service=FakeAuditService(),
    )

    login_step = await service.login(
        session,
        email="user@example.com",
        password="CorrectPassword!1",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert login_step.requires_2fa is True
    assert login_step.challenge_id is not None
    assert login_step.tokens is None

    challenge_key = f"login_challenge:{login_step.challenge_id}"
    assert challenge_key in redis.store
    payload = json.loads(redis.store[challenge_key])
    assert payload["user_id"] == str(user.id)
    assert "ip_address" not in payload
    assert "user_agent" not in payload
    assert isinstance(payload["ip_fingerprint"], str)
    assert isinstance(payload["user_agent_fingerprint"], str)

    token_pair = await service.verify_login_challenge(
        session,
        challenge_id=login_step.challenge_id,
        totp_code="123456",
        backup_code=None,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert token_pair.access_token == "access"
    assert token_pair.refresh_token == "refresh"
    assert challenge_key not in redis.store
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_login_challenge_rejects_context_mismatch() -> None:
    user = FakeUser(
        id=uuid4(),
        email="user@example.com",
        password_hash="hash",
        two_factor_enabled=True,
    )
    session = FakeSession()
    redis = FakeRedis()
    service = AuthService(
        settings=get_settings(),
        redis=redis,
        user_repository=FakeUserRepository(user),
        password_service=FakePasswordService(),
        refresh_token_service=FakeRefreshTokenService(),
        two_factor_service=FakeTwoFactorService(),
        brute_force_service=FakeBruteForceService(),
        audit_service=FakeAuditService(),
    )

    login_step = await service.login(
        session,
        email="user@example.com",
        password="CorrectPassword!1",
        ip_address="127.0.0.1",
        user_agent="pytest-agent",
    )

    with pytest.raises(InvalidChallengeException):
        await service.verify_login_challenge(
            session,
            challenge_id=login_step.challenge_id or "",
            totp_code="123456",
            backup_code=None,
            ip_address="127.0.0.2",
            user_agent="pytest-agent",
        )
    challenge_key = f"login_challenge:{login_step.challenge_id}"
    assert challenge_key not in redis.store
