from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.exceptions.auth import AccountLoginBlockedException, InvalidCredentialsException
from app.services.auth_service import AuthService
from app.services.refresh_token_service import TokenPair


@dataclass
class FakeUser:
    id: UUID
    email: str
    password_hash: str
    two_factor_enabled: bool = False
    is_active: bool = True
    login_blocked: bool = False


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.flush_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def flush(self) -> None:
        self.flush_calls += 1


class FakeRedis:
    async def set(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    async def get(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None

    async def delete(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        return None


class FakeUserRepository:
    def __init__(self, user: FakeUser) -> None:
        self.user = user

    async def get_by_email(self, session, email: str):
        _ = session
        return self.user if email == self.user.email else None


class FakePasswordService:
    def verify_password(self, password: str, password_hash: str) -> bool:
        return password == "good" and password_hash == self._expected

    def verify_against_dummy_hash(self, password: str) -> None:
        _ = password

    def __init__(self, expected_hash: str) -> None:
        self._expected = expected_hash


class FakeRefreshTokenService:
    async def issue_for_user(self, session, *, user_id: UUID, ip_address: str | None, user_agent: str | None):
        _ = (session, user_id, ip_address, user_agent)
        return TokenPair(
            access_token="access",
            refresh_token="refresh",
            access_expires_in=900,
            refresh_family_id=uuid4(),
            session_id=uuid4(),
        )


class FakeTwoFactorService:
    pass


class FakeAuditService:
    async def log_event(self, session, **kwargs) -> None:
        _ = (session, kwargs)


class FakeBruteForceService:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str], int] = {}

    async def assert_not_locked(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)

    async def record_failure(self, *, scope: str, identifier: str) -> int:
        key = (scope, identifier)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def clear_failures(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)


def _service(user: FakeUser) -> AuthService:
    return AuthService(
        settings=get_settings(),
        redis=FakeRedis(),
        user_repository=FakeUserRepository(user),
        password_service=FakePasswordService(user.password_hash),
        refresh_token_service=FakeRefreshTokenService(),
        two_factor_service=FakeTwoFactorService(),
        brute_force_service=FakeBruteForceService(),
        audit_service=FakeAuditService(),
    )


@pytest.mark.asyncio
async def test_third_wrong_password_sets_db_lock_and_raises_account_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRUTE_FORCE_LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("LOGIN_MAX_FAILED_ATTEMPTS", "3")
    get_settings.cache_clear()
    user = FakeUser(id=uuid4(), email="u@example.com", password_hash="h", two_factor_enabled=False)
    sess = FakeSession()
    service = _service(user)

    for _ in range(2):
        with pytest.raises(InvalidCredentialsException):
            await service.login(
                sess,
                email=user.email,
                password="bad",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )

    with pytest.raises(AccountLoginBlockedException):
        await service.login(
            sess,
            email=user.email,
            password="bad",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert user.login_blocked is True
    assert sess.flush_calls >= 1


@pytest.mark.asyncio
async def test_login_blocked_before_password_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRUTE_FORCE_LOGIN_MAX_ATTEMPTS", "3")
    get_settings.cache_clear()
    user = FakeUser(
        id=uuid4(),
        email="u@example.com",
        password_hash="h",
        two_factor_enabled=False,
        login_blocked=True,
    )
    sess = FakeSession()
    service = _service(user)

    with pytest.raises(AccountLoginBlockedException):
        await service.login(
            sess,
            email=user.email,
            password="good",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
