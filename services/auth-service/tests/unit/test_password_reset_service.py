from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.exceptions.auth import (
    BadRequestException,
    PasswordResetFlowBlockedException,
    ServiceUnavailableException,
)
from app.services.password_reset_service import PasswordResetService


@dataclass
class FakeUser:
    id: UUID
    email: str
    password_hash: str = "old-hash"
    password_reset_blocked: bool = False
    login_blocked: bool = False


@dataclass
class FakeResetRecord:
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None


class FakeSession:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self.flush_calls = 0

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def flush(self) -> None:
        self.flush_calls += 1


class FakeUserRepository:
    def __init__(self, user: FakeUser | None) -> None:
        self.user = user

    async def get_by_email(self, session, email: str):
        _ = session
        return self.user if self.user and email == self.user.email else None

    async def update_password(self, user: FakeUser, password_hash: str) -> None:
        user.password_hash = password_hash


class FakePasswordService:
    def hash_password(self, password: str) -> str:
        return f"hashed:{password}"


class FakePasswordResetRepository:
    def __init__(self) -> None:
        self.records: list[FakeResetRecord] = []

    async def mark_active_for_user_used(self, session, *, user_id: UUID, used_at: datetime) -> None:
        _ = session
        for record in self.records:
            if record.user_id == user_id and record.used_at is None:
                record.used_at = used_at

    async def create(
        self,
        session,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        requested_ip: str | None,
        requested_user_agent: str | None,
    ) -> FakeResetRecord:
        _ = (session, requested_ip, requested_user_agent)
        record = FakeResetRecord(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.records.append(record)
        return record

    async def get_active_for_user_by_hash(self, session, *, user_id: UUID, token_hash: str):
        _ = session
        for record in self.records:
            if (
                record.user_id == user_id
                and record.token_hash == token_hash
                and record.used_at is None
            ):
                return record
        return None

    async def mark_used(self, token: FakeResetRecord, used_at: datetime) -> None:
        token.used_at = used_at


class FakeRefreshTokenRepository:
    def __init__(self) -> None:
        self.revoked_for_user: UUID | None = None

    async def revoke_all_for_user(self, session, user_id: UUID, reason: str) -> None:
        _ = (session, reason)
        self.revoked_for_user = user_id


class FakeSessionService:
    def __init__(self) -> None:
        self.revoked_for_user: UUID | None = None
        self.active_session_ids = [uuid4(), uuid4()]

    async def list_active_session_ids_for_user(self, session, user_id: UUID) -> list[UUID]:
        _ = (session, user_id)
        return self.active_session_ids

    async def revoke_user_sessions(self, session, user_id: UUID) -> None:
        _ = session
        self.revoked_for_user = user_id


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, int | None]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = (value, ex)


class FakeEmailProvider:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(self, *, to_email: str, subject: str, body: str) -> bool:
        self.messages.append({"to_email": to_email, "subject": subject, "body": body})
        return True


class FakeAuditService:
    async def log_event(self, session, **kwargs) -> None:
        _ = (session, kwargs)


class FakeBruteForceService:
    def __init__(self) -> None:
        self.failures: list[tuple[str, str]] = []
        self.cleared: list[tuple[str, str]] = []
        self._counts: dict[tuple[str, str], int] = {}

    async def assert_not_locked(self, *, scope: str, identifier: str) -> None:
        _ = (scope, identifier)

    async def record_failure(self, *, scope: str, identifier: str) -> int:
        self.failures.append((scope, identifier))
        key = (scope, identifier)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def clear_failures(self, *, scope: str, identifier: str) -> None:
        self.cleared.append((scope, identifier))


def _build_service(user: FakeUser | None):
    reset_repository = FakePasswordResetRepository()
    refresh_repository = FakeRefreshTokenRepository()
    session_service = FakeSessionService()
    redis = FakeRedis()
    email_provider = FakeEmailProvider()
    brute_force_service = FakeBruteForceService()
    service = PasswordResetService(
        settings=get_settings(),
        user_repository=FakeUserRepository(user),
        password_service=FakePasswordService(),
        password_reset_repository=reset_repository,
        refresh_token_repository=refresh_repository,
        session_service=session_service,
        redis=redis,
        email_provider=email_provider,
        audit_service=FakeAuditService(),
        brute_force_service=brute_force_service,
    )
    return (
        service,
        reset_repository,
        refresh_repository,
        session_service,
        redis,
        email_provider,
        brute_force_service,
    )


@pytest.mark.asyncio
async def test_request_reset_email_failure_returns_service_unavailable() -> None:
    class BoomEmail(FakeEmailProvider):
        async def send(self, *, to_email: str, subject: str, body: str) -> None:
            _ = (to_email, subject, body)
            raise OSError("smtp down")

    user = FakeUser(id=uuid4(), email="user@example.com")
    service, *_rest = _build_service(user)
    service.email_provider = BoomEmail()

    sess = FakeSession()
    with pytest.raises(ServiceUnavailableException):
        await service.request_reset(
            sess,
            email=user.email,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
    assert sess.rollback_calls == 1


@pytest.mark.asyncio
async def test_request_reset_invalidates_existing_active_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = FakeUser(id=uuid4(), email="user@example.com")
    service, reset_repository, *_rest = _build_service(user)

    monkeypatch.setattr(service, "_generate_code", lambda: "111111")
    await service.request_reset(
        FakeSession(),
        email=user.email,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    monkeypatch.setattr(service, "_generate_code", lambda: "222222")
    await service.request_reset(
        FakeSession(),
        email=user.email,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert len(reset_repository.records) == 2
    assert reset_repository.records[0].used_at is not None
    assert reset_repository.records[1].used_at is None


@pytest.mark.asyncio
async def test_reset_password_records_failures_and_clears_on_success() -> None:
    user = FakeUser(id=uuid4(), email="user@example.com")
    (
        service,
        reset_repository,
        refresh_repository,
        session_service,
        redis,
        _email_provider,
        brute_force_service,
    ) = _build_service(user)
    session = FakeSession()

    await service.request_reset(
        session,
        email=user.email,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    with pytest.raises(BadRequestException):
        await service.reset_password(
            session,
            email=user.email,
            code="000000",
            new_password="NewPassw0rd!",
            ip_address="127.0.0.1",
            user_agent="pytest",
        )

    assert brute_force_service.failures == [
        ("password_reset", "user@example.com:127.0.0.1"),
        ("password_reset_account", "user@example.com"),
    ]

    raw_code = service._generate_code()
    reset_repository.records.clear()
    token_hash = service._hash_token(raw_code)
    await reset_repository.create(
        session,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
        requested_ip=None,
        requested_user_agent=None,
    )

    await service.reset_password(
        session,
        email=user.email,
        code=raw_code,
        new_password="NewPassw0rd!",
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert user.password_hash == "hashed:NewPassw0rd!"
    assert refresh_repository.revoked_for_user == user.id
    assert session_service.revoked_for_user == user.id
    assert len(redis.values) == len(session_service.active_session_ids)
    assert all(key.startswith("access_session_revoked:") for key in redis.values)
    assert brute_force_service.cleared == [
        ("password_reset", "user@example.com:127.0.0.1"),
        ("password_reset_account", "user@example.com"),
    ]


@pytest.mark.asyncio
async def test_request_reset_raises_when_password_reset_blocked() -> None:
    user = FakeUser(id=uuid4(), email="blocked@example.com", password_reset_blocked=True)
    service, *_ = _build_service(user)
    with pytest.raises(PasswordResetFlowBlockedException):
        await service.request_reset(
            FakeSession(),
            email=user.email,
            ip_address=None,
            user_agent=None,
        )


@pytest.mark.asyncio
async def test_reset_password_raises_when_password_reset_blocked() -> None:
    user = FakeUser(id=uuid4(), email="blocked2@example.com", password_reset_blocked=True)
    service, *_ = _build_service(user)
    with pytest.raises(PasswordResetFlowBlockedException):
        await service.reset_password(
            FakeSession(),
            email=user.email,
            code="123456",
            new_password="NewPassw0rd!",
            ip_address=None,
            user_agent=None,
        )


@pytest.mark.asyncio
async def test_three_wrong_reset_codes_persist_password_reset_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BRUTE_FORCE_PASSWORD_RESET_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("RESET_CODE_MAX_FAILED_ATTEMPTS", "3")
    get_settings.cache_clear()
    user = FakeUser(id=uuid4(), email="user@example.com")
    service, *_rest = _build_service(user)
    session = FakeSession()

    for _ in range(3):
        with pytest.raises(BadRequestException):
            await service.reset_password(
                session,
                email=user.email,
                code="000000",
                new_password="NewPassw0rd!",
                ip_address="127.0.0.1",
                user_agent="pytest",
            )

    assert user.password_reset_blocked is True
    assert session.commit_calls >= 1
    sync/local-main-2026-04-19


@pytest.mark.asyncio
async def test_request_reset_unconfigured_smtp_allow_missing_no_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    monkeypatch.setenv("AUTH_ALLOW_MISSING_SMTP", "true")
    get_settings.cache_clear()
    user = FakeUser(id=uuid4(), email="nomail@example.com")
    service, reset_repository, *_rest = _build_service(user)
    result = await service.request_reset(
        FakeSession(),
        email=user.email,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert result.email_sent is False
    assert reset_repository.records == []
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_request_reset_unconfigured_smtp_strict_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    monkeypatch.setenv("AUTH_ALLOW_MISSING_SMTP", "false")
    get_settings.cache_clear()
    user = FakeUser(id=uuid4(), email="strict@example.com")
    service, *_rest = _build_service(user)
    with pytest.raises(ServiceUnavailableException):
        await service.request_reset(
            FakeSession(),
            email=user.email,
            ip_address="127.0.0.1",
            user_agent="pytest",
        )
    get_settings.cache_clear()
    main
