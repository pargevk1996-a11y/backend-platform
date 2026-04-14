from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload
from sqlalchemy.sql import Select

from app.models.password_reset_token import PasswordResetToken


class PasswordResetRepository:
    @staticmethod
    def _build_get_by_hash_for_update_stmt(token_hash: str) -> Select[tuple[PasswordResetToken]]:
        return (
            select(PasswordResetToken)
            .options(lazyload(PasswordResetToken.user))
            .where(PasswordResetToken.token_hash == token_hash)
            .with_for_update(of=PasswordResetToken)
        )

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
        requested_ip: str | None,
        requested_user_agent: str | None,
    ) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            requested_ip=requested_ip,
            requested_user_agent=requested_user_agent,
        )
        session.add(token)
        await session.flush()
        return token

    async def mark_active_for_user_used(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        used_at: datetime,
    ) -> None:
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=used_at)
        )
        await session.execute(stmt)

    async def get_active_for_user_by_hash(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        token_hash: str,
    ) -> PasswordResetToken | None:
        stmt = self._build_get_by_hash_for_update_stmt(token_hash).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken, used_at: datetime) -> None:
        token.used_at = used_at
