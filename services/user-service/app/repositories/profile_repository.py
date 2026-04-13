from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserProfile


class ProfileRepository:
    async def get_by_user_id(self, session: AsyncSession, user_id: UUID) -> UserProfile | None:
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        session: AsyncSession,
        *,
        profile: UserProfile,
        display_name: str | None,
        locale: str,
        timezone: str,
        avatar_url: str | None,
    ) -> UserProfile:
        profile.display_name = display_name
        profile.locale = locale
        profile.timezone = timezone
        profile.avatar_url = avatar_url
        await session.flush()
        return profile
