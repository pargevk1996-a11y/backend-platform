from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload
from sqlalchemy.sql import Select

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    @staticmethod
    def _build_get_by_jti_for_update_stmt(jti: UUID) -> Select[tuple[RefreshToken]]:
        return (
            select(RefreshToken)
            .options(lazyload(RefreshToken.user))
            .where(RefreshToken.jti == jti)
            .with_for_update(of=RefreshToken)
        )

    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        jti: UUID,
        family_id: UUID,
        parent_jti: UUID | None,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            family_id=family_id,
            parent_jti=parent_jti,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.add(token)
        await session.flush()
        return token

    async def get_by_jti_for_update(self, session: AsyncSession, jti: UUID) -> RefreshToken | None:
        stmt = self._build_get_by_jti_for_update_stmt(jti)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_token(
        self,
        session: AsyncSession,
        *,
        token: RefreshToken,
        reason: str,
        replaced_by_jti: UUID | None = None,
    ) -> None:
        token.revoked_at = datetime.now(tz=UTC)
        token.revocation_reason = reason
        token.replaced_by_jti = replaced_by_jti

    async def mark_rotated(
        self,
        session: AsyncSession,
        *,
        token: RefreshToken,
        replaced_by_jti: UUID,
    ) -> bool:
        now = datetime.now(tz=UTC)
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.id == token.id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.rotated_at.is_(None),
            )
            .values(
                rotated_at=now,
                revoked_at=now,
                revocation_reason="rotated",
                replaced_by_jti=replaced_by_jti,
            )
        )
        result = await session.execute(stmt)
        if result.rowcount != 1:
            return False
        token.rotated_at = now
        token.revoked_at = now
        token.revocation_reason = "rotated"
        token.replaced_by_jti = replaced_by_jti
        return True

    async def revoke_family(self, session: AsyncSession, family_id: UUID, reason: str) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=UTC), revocation_reason=reason)
        )
        await session.execute(stmt)

    async def revoke_all_for_user(self, session: AsyncSession, user_id: UUID, reason: str) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(tz=UTC), revocation_reason=reason)
        )
        await session.execute(stmt)
