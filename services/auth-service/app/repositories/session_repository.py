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

    async def touch_family(self, session: AsyncSession, refresh_family_id: UUID) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.refresh_family_id == refresh_family_id, UserSession.revoked_at.is_(None)
            )
            .values(last_seen_at=datetime.now(tz=UTC))
        )
        await session.execute(stmt)

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

    async def revoke_user_sessions(self, session: AsyncSession, user_id: UUID) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=UTC))
        )
        await session.execute(stmt)
