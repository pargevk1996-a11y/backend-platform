from __future__ import annotations

import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.exceptions.auth import BadRequestException
from app.exceptions.two_factor import (
    InvalidTwoFactorCodeException,
    TwoFactorAlreadyEnabledException,
    TwoFactorNotEnabledException,
)
from app.integrations.totp.generator import generate_secret, provisioning_uri
from app.integrations.totp.qr_code import generate_qr_png_base64
from app.integrations.totp.verifier import verify_totp_code
from app.models.user import User
from app.repositories.two_factor_repository import TwoFactorRepository
from app.services.password_service import PasswordService


@dataclass(slots=True)
class TwoFactorSetupData:
    secret: str
    qr_png_base64: str


@dataclass(slots=True)
class GeneratedBackupCodes:
    plain_codes: list[str]


class TwoFactorService:
    """Service handling TOTP setup, verification, and backup codes."""

    def __init__(
        self,
        *,
        settings: Settings,
        repository: TwoFactorRepository,
        password_service: PasswordService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.password_service = password_service
        self._fernet = Fernet(settings.totp_encryption_key_value)

    def _encrypt_secret(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

    def _decrypt_secret(self, encrypted_secret: str) -> str:
        return self._fernet.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")

    async def create_setup(self, session: AsyncSession, *, user: User) -> TwoFactorSetupData:
        if user.two_factor_enabled:
            raise TwoFactorAlreadyEnabledException()

        secret = generate_secret()
        encrypted_secret = self._encrypt_secret(secret)
        await self.repository.upsert_secret(
            session, user_id=user.id, encrypted_secret=encrypted_secret
        )

        uri = provisioning_uri(
            secret=secret,
            account_name=user.email,
            issuer_name=self.settings.totp_issuer,
        )
        qr_png_base64 = generate_qr_png_base64(uri)
        return TwoFactorSetupData(secret=secret, qr_png_base64=qr_png_base64)

    async def enable(
        self, session: AsyncSession, *, user: User, totp_code: str
    ) -> GeneratedBackupCodes:
        if user.two_factor_enabled:
            raise TwoFactorAlreadyEnabledException()

        secret_record = await self.repository.get_secret_for_update(session, user.id)
        if secret_record is None:
            raise BadRequestException("2FA setup has not been initialized")

        secret = self._decrypt_secret(secret_record.encrypted_secret)
        is_valid, timecode = verify_totp_code(
            secret=secret,
            code=totp_code,
            interval_seconds=self.settings.totp_interval_seconds,
            valid_window=1,
        )
        if not is_valid:
            raise InvalidTwoFactorCodeException()

        await self.repository.confirm_secret(
            session, record=secret_record, last_used_timecode=timecode
        )
        user.two_factor_enabled = True

        plain_codes = self._generate_plain_backup_codes(10)
        hashed_codes = [self.password_service.hash_backup_code(code) for code in plain_codes]
        await self.repository.replace_backup_codes(session, user_id=user.id, hashes=hashed_codes)
        return GeneratedBackupCodes(plain_codes=plain_codes)

    async def verify_for_login(
        self,
        session: AsyncSession,
        *,
        user: User,
        totp_code: str | None,
        backup_code: str | None,
    ) -> None:
        if not user.two_factor_enabled:
            raise TwoFactorNotEnabledException()

        if bool(totp_code) == bool(backup_code):
            raise BadRequestException("Provide either totp_code or backup_code")

        if totp_code:
            await self._verify_totp(session, user=user, totp_code=totp_code)
            return

        await self._verify_backup_code(session, user=user, backup_code=backup_code or "")

    async def disable(
        self,
        session: AsyncSession,
        *,
        user: User,
        totp_code: str | None,
        backup_code: str | None,
    ) -> None:
        await self.verify_for_login(
            session,
            user=user,
            totp_code=totp_code,
            backup_code=backup_code,
        )
        await self.repository.delete_two_factor_data(session, user.id)
        user.two_factor_enabled = False

    async def regenerate_backup_codes(
        self,
        session: AsyncSession,
        *,
        user: User,
        totp_code: str | None,
        backup_code: str | None,
    ) -> GeneratedBackupCodes:
        await self.verify_for_login(
            session,
            user=user,
            totp_code=totp_code,
            backup_code=backup_code,
        )
        plain_codes = self._generate_plain_backup_codes(10)
        hashed_codes = [self.password_service.hash_backup_code(code) for code in plain_codes]
        await self.repository.replace_backup_codes(session, user_id=user.id, hashes=hashed_codes)
        return GeneratedBackupCodes(plain_codes=plain_codes)

    async def _verify_totp(self, session: AsyncSession, *, user: User, totp_code: str) -> None:
        secret_record = await self.repository.get_secret(session, user.id)
        if secret_record is None or secret_record.confirmed_at is None:
            raise TwoFactorNotEnabledException()

        secret = self._decrypt_secret(secret_record.encrypted_secret)
        is_valid, timecode = verify_totp_code(
            secret=secret,
            code=totp_code,
            interval_seconds=self.settings.totp_interval_seconds,
            valid_window=1,
        )
        if not is_valid:
            raise InvalidTwoFactorCodeException()

        if (
            secret_record.last_used_timecode is not None
            and timecode <= secret_record.last_used_timecode
        ):
            raise InvalidTwoFactorCodeException()

        await self.repository.update_last_used_timecode(
            session,
            record=secret_record,
            last_used_timecode=timecode,
        )

    async def _verify_backup_code(
        self, session: AsyncSession, *, user: User, backup_code: str
    ) -> None:
        codes = await self.repository.list_backup_codes_for_update(session, user.id)
        for candidate in codes:
            if candidate.used_at is not None:
                continue
            if self.password_service.verify_backup_code(backup_code, candidate.code_hash):
                await self.repository.mark_backup_code_used(session, backup_code=candidate)
                return
        raise InvalidTwoFactorCodeException()

    @staticmethod
    def _generate_plain_backup_codes(count: int) -> list[str]:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        return [
            "".join(secrets.choice(alphabet) for _ in range(4))
            + "-"
            + "".join(secrets.choice(alphabet) for _ in range(4))
            for _ in range(count)
        ]
