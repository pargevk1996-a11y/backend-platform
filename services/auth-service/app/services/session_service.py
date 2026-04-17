from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession
from app.repositories.session_repository import SessionRepository


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self.repository = repository

    async def create_session(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        refresh_family_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserSession:
        return await self.repository.create(
            session,
            user_id=user_id,
            refresh_family_id=refresh_family_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def revoke_family(self, session: AsyncSession, refresh_family_id: UUID) -> None:
        await self.repository.revoke_family(session, refresh_family_id)

    async def touch_family(self, session: AsyncSession, refresh_family_id: UUID) -> None:
        await self.repository.touch_family(session, refresh_family_id)

    async def touch_session_activity(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        idle_timeout_seconds: int,
    ) -> UserSession | None:
        user_session = await self.repository.get_by_id_for_update(session, session_id)
        if user_session is None:
            return None

        now = datetime.now(tz=UTC)
        idle_threshold = now - timedelta(seconds=idle_timeout_seconds)
        if user_session.last_seen_at < idle_threshold:
            await self.repository.revoke_family(session, user_session.refresh_family_id)
            return None

        await self.repository.touch_session(session, user_session=user_session, seen_at=now)
        return user_session

    async def is_family_active(self, session: AsyncSession, refresh_family_id: UUID) -> bool:
        return await self.repository.is_family_active(session, refresh_family_id)

    async def list_active_session_ids_for_user(
        self, session: AsyncSession, user_id: UUID
    ) -> list[UUID]:
        return await self.repository.list_active_session_ids_for_user(session, user_id)

    async def revoke_user_sessions(self, session: AsyncSession, user_id: UUID) -> None:
        await self.repository.revoke_user_sessions(session, user_id)
