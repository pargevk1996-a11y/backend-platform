from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup_code import BackupCode
from app.models.two_factor_secret import TwoFactorSecret


class TwoFactorRepository:
    async def get_secret(self, session: AsyncSession, user_id: UUID) -> TwoFactorSecret | None:
        stmt = select(TwoFactorSecret).where(TwoFactorSecret.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_secret(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        encrypted_secret: str,
    ) -> TwoFactorSecret:
        record = await self.get_secret(session, user_id)
        if record is None:
            record = TwoFactorSecret(user_id=user_id, encrypted_secret=encrypted_secret)
            session.add(record)
        else:
            record.encrypted_secret = encrypted_secret
            record.confirmed_at = None
            record.last_used_timecode = None
        await session.flush()
        return record

    async def confirm_secret(
        self,
        session: AsyncSession,
        *,
        record: TwoFactorSecret,
        last_used_timecode: int,
    ) -> None:
        record.confirmed_at = datetime.now(tz=timezone.utc)
        record.last_used_timecode = last_used_timecode

    async def update_last_used_timecode(
        self,
        session: AsyncSession,
        *,
        record: TwoFactorSecret,
        last_used_timecode: int,
    ) -> None:
        record.last_used_timecode = last_used_timecode

    async def list_backup_codes(self, session: AsyncSession, user_id: UUID) -> list[BackupCode]:
        stmt = select(BackupCode).where(BackupCode.user_id == user_id).order_by(BackupCode.created_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def replace_backup_codes(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        hashes: list[str],
    ) -> None:
        await session.execute(delete(BackupCode).where(BackupCode.user_id == user_id))
        session.add_all([BackupCode(user_id=user_id, code_hash=value) for value in hashes])

    async def mark_backup_code_used(self, session: AsyncSession, *, backup_code: BackupCode) -> None:
        backup_code.used_at = datetime.now(tz=timezone.utc)

    async def delete_two_factor_data(self, session: AsyncSession, user_id: UUID) -> None:
        await session.execute(delete(BackupCode).where(BackupCode.user_id == user_id))
        await session.execute(delete(TwoFactorSecret).where(TwoFactorSecret.user_id == user_id))
