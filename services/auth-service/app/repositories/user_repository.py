from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_for_update(self, session: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower()).with_for_update(of=User)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, email: str, password_hash: str) -> User:
        user = User(email=email.lower(), password_hash=password_hash)
        session.add(user)
        await session.flush()
        return user

    async def update_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash

    async def record_failed_login(
        self,
        user: User,
        *,
        lock_threshold: int,
        reason: str,
    ) -> bool:
        user.failed_login_count += 1
        if user.failed_login_count >= lock_threshold and user.locked_at is None:
            user.locked_at = datetime.now(tz=UTC)
            user.lock_reason = reason
        return user.locked_at is not None

    async def clear_login_failures(self, user: User) -> None:
        user.failed_login_count = 0

    async def clear_login_lock(self, user: User) -> None:
        user.failed_login_count = 0
        user.locked_at = None
        user.lock_reason = None
