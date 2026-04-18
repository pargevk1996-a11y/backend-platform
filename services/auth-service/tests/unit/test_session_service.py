from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.services.session_service import SessionService


@dataclass
class FakeSessionRecord:
    id: object
    refresh_family_id: object
    last_seen_at: datetime


class FakeSessionRepository:
    def __init__(self) -> None:
        self.record: FakeSessionRecord | None = None
        self.revoked_family_id = None

    async def get_by_id_for_update(self, session, session_id):
        _ = (session, session_id)
        return self.record

    async def revoke_family(self, session, refresh_family_id):
        _ = session
        self.revoked_family_id = refresh_family_id

    async def touch_session(self, session, *, user_session, seen_at):
        _ = session
        user_session.last_seen_at = seen_at


@pytest.mark.asyncio
async def test_touch_session_activity_updates_recent_session() -> None:
    repository = FakeSessionRepository()
    repository.record = FakeSessionRecord(
        id=uuid4(),
        refresh_family_id=uuid4(),
        last_seen_at=datetime.now(tz=UTC) - timedelta(minutes=5),
    )
    service = SessionService(repository)

    updated = await service.touch_session_activity(
        None,
        session_id=repository.record.id,
        idle_timeout_seconds=1800,
    )

    assert updated is repository.record
    assert repository.revoked_family_id is None
    assert repository.record.last_seen_at > datetime.now(tz=UTC) - timedelta(seconds=5)


@pytest.mark.asyncio
async def test_touch_session_activity_revokes_idle_session() -> None:
    repository = FakeSessionRepository()
    repository.record = FakeSessionRecord(
        id=uuid4(),
        refresh_family_id=uuid4(),
        last_seen_at=datetime.now(tz=UTC) - timedelta(minutes=31),
    )
    service = SessionService(repository)

    updated = await service.touch_session_activity(
        None,
        session_id=repository.record.id,
        idle_timeout_seconds=1800,
    )

    assert updated is None
    assert repository.revoked_family_id == repository.record.refresh_family_id
