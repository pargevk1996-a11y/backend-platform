from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.exceptions.token import TokenReuseDetectedException
from app.services.jwt_service import JWTService
from app.services.refresh_token_service import RefreshTokenService


@dataclass
class FakeRefreshRecord:
    user_id: UUID
    jti: UUID
    family_id: UUID
    parent_jti: UUID | None
    token_hash: str
    expires_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    revoked_at: datetime | None = None
    rotated_at: datetime | None = None
    replaced_by_jti: UUID | None = None
    revocation_reason: str | None = None


class FakeRefreshRepo:
    def __init__(self) -> None:
        self.records: dict[UUID, FakeRefreshRecord] = {}

    async def create(self, session, **kwargs):
        record = FakeRefreshRecord(**kwargs)
        self.records[record.jti] = record
        return record

    async def get_by_jti_for_update(self, session, jti: UUID):
        return self.records.get(jti)

    async def mark_rotated(self, session, *, token: FakeRefreshRecord, replaced_by_jti: UUID):
        token.rotated_at = datetime.now(tz=UTC)
        token.revoked_at = datetime.now(tz=UTC)
        token.revocation_reason = "rotated"
        token.replaced_by_jti = replaced_by_jti

    async def revoke_family(self, session, family_id: UUID, reason: str):
        for record in self.records.values():
            if record.family_id == family_id and record.revoked_at is None:
                record.revoked_at = datetime.now(tz=UTC)
                record.revocation_reason = reason

    async def revoke_token(
        self, session, *, token: FakeRefreshRecord, reason: str, replaced_by_jti=None
    ):
        token.revoked_at = datetime.now(tz=UTC)
        token.revocation_reason = reason
        token.replaced_by_jti = replaced_by_jti


class FakeSessionService:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.active_families: set[UUID] = set()

    async def create_session(self, session, *, user_id, refresh_family_id, ip_address, user_agent):
        _ = (user_id, refresh_family_id, ip_address, user_agent)
        self.active_families.add(refresh_family_id)
        return SimpleNamespace(id=self.session_id)

    async def revoke_family(self, session, refresh_family_id: UUID):
        self.active_families.discard(refresh_family_id)

    async def touch_family(self, session, refresh_family_id: UUID):
        _ = refresh_family_id

    async def is_family_active(self, session, refresh_family_id: UUID) -> bool:
        _ = session
        return refresh_family_id in self.active_families


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        _ = ex
        self.values[key] = value


@pytest.mark.asyncio
async def test_refresh_token_rotation() -> None:
    settings = get_settings()
    jwt_service = JWTService(settings)
    repo = FakeRefreshRepo()
    session_service = FakeSessionService()
    redis = FakeRedis()

    service = RefreshTokenService(
        settings=settings,
        repository=repo,
        jwt_service=jwt_service,
        session_service=session_service,
        rotation_retry_cache=redis,
    )

    user_id = uuid4()
    issued = await service.issue_for_user(
        None,
        user_id=user_id,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    rotated = await service.rotate(
        None,
        raw_refresh_token=issued.refresh_token,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert rotated.refresh_token != issued.refresh_token
    assert rotated.access_token != issued.access_token
    assert rotated.refresh_family_id == issued.refresh_family_id


@pytest.mark.asyncio
async def test_reusing_rotated_refresh_token_revokes_family() -> None:
    settings = get_settings()
    jwt_service = JWTService(settings)
    repo = FakeRefreshRepo()
    session_service = FakeSessionService()
    redis = FakeRedis()
    service = RefreshTokenService(
        settings=settings,
        repository=repo,
        jwt_service=jwt_service,
        session_service=session_service,
        rotation_retry_cache=redis,
    )
    issued = await service.issue_for_user(
        None,
        user_id=uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    await service.rotate(
        None,
        raw_refresh_token=issued.refresh_token,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    with pytest.raises(TokenReuseDetectedException):
        await service.rotate(
            None,
            raw_refresh_token=issued.refresh_token,
            ip_address="127.0.0.2",
            user_agent="pytest",
        )

    assert issued.refresh_family_id not in session_service.active_families
    assert all(
        record.revoked_at is not None
        for record in repo.records.values()
        if record.family_id == issued.refresh_family_id
    )


@pytest.mark.asyncio
async def test_retrying_recent_refresh_rotation_returns_cached_pair_without_revoking_family() -> None:
    settings = get_settings()
    jwt_service = JWTService(settings)
    repo = FakeRefreshRepo()
    session_service = FakeSessionService()
    redis = FakeRedis()
    service = RefreshTokenService(
        settings=settings,
        repository=repo,
        jwt_service=jwt_service,
        session_service=session_service,
        rotation_retry_cache=redis,
    )
    issued = await service.issue_for_user(
        None,
        user_id=uuid4(),
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    rotated = await service.rotate(
        None,
        raw_refresh_token=issued.refresh_token,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    retried = await service.rotate(
        None,
        raw_refresh_token=issued.refresh_token,
        ip_address="127.0.0.2",
        user_agent="pytest",
    )

    assert retried.refresh_token == rotated.refresh_token
    assert retried.access_token == rotated.access_token
    assert issued.refresh_family_id in session_service.active_families
