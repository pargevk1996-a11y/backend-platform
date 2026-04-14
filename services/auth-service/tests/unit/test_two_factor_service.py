from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pyotp
import pytest
from app.core.config import get_settings
from app.exceptions.two_factor import InvalidTwoFactorCodeException
from app.integrations.totp import verifier as totp_verifier
from app.services.password_service import PasswordService
from app.services.two_factor_service import TwoFactorService


@dataclass
class FakeSecretRecord:
    user_id: UUID
    encrypted_secret: str
    confirmed_at: datetime | None = None
    last_used_timecode: int | None = None


@dataclass
class FakeBackupCode:
    code_hash: str
    used_at: datetime | None = None


class FakeTwoFactorRepository:
    def __init__(self) -> None:
        self.secret: FakeSecretRecord | None = None
        self.backup_codes: list[FakeBackupCode] = []

    async def get_secret(self, session, user_id: UUID):
        return self.secret

    async def get_secret_for_update(self, session, user_id: UUID):
        return self.secret

    async def upsert_secret(self, session, *, user_id: UUID, encrypted_secret: str):
        self.secret = FakeSecretRecord(user_id=user_id, encrypted_secret=encrypted_secret)
        return self.secret

    async def confirm_secret(self, session, *, record: FakeSecretRecord, last_used_timecode: int):
        record.confirmed_at = datetime.now(tz=UTC)
        record.last_used_timecode = last_used_timecode

    async def update_last_used_timecode(
        self, session, *, record: FakeSecretRecord, last_used_timecode: int
    ):
        record.last_used_timecode = last_used_timecode

    async def list_backup_codes(self, session, user_id: UUID):
        return self.backup_codes

    async def list_backup_codes_for_update(self, session, user_id: UUID):
        return self.backup_codes

    async def replace_backup_codes(self, session, *, user_id: UUID, hashes: list[str]):
        self.backup_codes = [FakeBackupCode(code_hash=value) for value in hashes]

    async def mark_backup_code_used(self, session, *, backup_code: FakeBackupCode):
        backup_code.used_at = datetime.now(tz=UTC)

    async def delete_two_factor_data(self, session, user_id: UUID):
        self.secret = None
        self.backup_codes = []


@pytest.mark.asyncio
async def test_two_factor_setup_enable_and_backup_login() -> None:
    settings = get_settings()
    repo = FakeTwoFactorRepository()
    password_service = PasswordService(settings)
    service = TwoFactorService(
        settings=settings, repository=repo, password_service=password_service
    )

    user = SimpleNamespace(id=uuid4(), email="user@example.com", two_factor_enabled=False)

    setup = await service.create_setup(None, user=user)
    totp = pyotp.TOTP(setup.secret, interval=settings.totp_interval_seconds)
    current_code = totp.now()

    generated = await service.enable(None, user=user, totp_code=current_code)
    assert user.two_factor_enabled is True
    assert len(generated.plain_codes) == 10

    backup_code = generated.plain_codes[0]
    await service.verify_for_login(None, user=user, totp_code=None, backup_code=backup_code)

    with pytest.raises(InvalidTwoFactorCodeException):
        await service.verify_for_login(None, user=user, totp_code=None, backup_code=backup_code)


@pytest.mark.asyncio
async def test_totp_replay_from_previous_window_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    repo = FakeTwoFactorRepository()
    password_service = PasswordService(settings)
    service = TwoFactorService(
        settings=settings, repository=repo, password_service=password_service
    )
    user = SimpleNamespace(id=uuid4(), email="user@example.com", two_factor_enabled=False)

    monkeypatch.setattr(totp_verifier.time, "time", lambda: 1_000)
    setup = await service.create_setup(None, user=user)
    totp = pyotp.TOTP(setup.secret, interval=settings.totp_interval_seconds)
    code = totp.at(1_000)
    await service.enable(None, user=user, totp_code=code)

    monkeypatch.setattr(totp_verifier.time, "time", lambda: 1_030)
    with pytest.raises(InvalidTwoFactorCodeException):
        await service.verify_for_login(None, user=user, totp_code=code, backup_code=None)
