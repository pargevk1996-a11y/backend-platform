from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_user import AppUser
from app.models.user_profile import UserProfile


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: UUID) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_subject(self, session: AsyncSession, subject: str) -> AppUser | None:
        stmt = select(AppUser).where(AppUser.external_subject == subject)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, *, user_id: UUID, external_subject: str) -> AppUser:
        user = AppUser(id=user_id, external_subject=external_subject)
        session.add(user)
        session.add(UserProfile(user_id=user_id))
        await session.flush()
        return user
