from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession


class SessionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        refresh_family_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserSession:
        user_session = UserSession(
            user_id=user_id,
            refresh_family_id=refresh_family_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(user_session)
        await session.flush()
        return user_session

    async def revoke_family(self, session: AsyncSession, refresh_family_id: UUID) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.refresh_family_id == refresh_family_id, UserSession.revoked_at.is_(None)
            )
            .values(revoked_at=datetime.now(tz=UTC))
        )
        await session.execute(stmt)

    async def get_by_id_for_update(
        self,
        session: AsyncSession,
        session_id: UUID,
    ) -> UserSession | None:
        stmt = (
            select(UserSession)
            .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
            .with_for_update(of=UserSession)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def touch_family(self, session: AsyncSession, refresh_family_id: UUID) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.refresh_family_id == refresh_family_id, UserSession.revoked_at.is_(None)
            )
            .values(last_seen_at=datetime.now(tz=UTC))
        )
        await session.execute(stmt)

    async def touch_session(
        self,
        session: AsyncSession,
        *,
        user_session: UserSession,
        seen_at: datetime,
    ) -> None:
        _ = session
        user_session.last_seen_at = seen_at

    async def is_family_active(self, session: AsyncSession, refresh_family_id: UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(UserSession)
            .where(
                UserSession.refresh_family_id == refresh_family_id,
                UserSession.revoked_at.is_(None),
            )
        )
        result = await session.execute(stmt)
        return int(result.scalar_one()) > 0

    async def list_active_session_ids_for_user(
        self, session: AsyncSession, user_id: UUID
    ) -> list[UUID]:
        stmt = select(UserSession.id).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_user_sessions(self, session: AsyncSession, user_id: UUID) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=UTC))
        )
        await session.execute(stmt)
