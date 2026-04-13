from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.exceptions.auth import BadRequestException
from app.services.password_service import PasswordService


@pytest.mark.asyncio
async def test_hash_and_verify_password() -> None:
    service = PasswordService(get_settings())
    password = "StrongPassw0rd!"
    password_hash = service.hash_password(password)

    assert password_hash != password
    assert service.verify_password(password, password_hash)
    assert not service.verify_password("WrongPassw0rd!", password_hash)


@pytest.mark.asyncio
async def test_password_policy_rejects_weak_password() -> None:
    service = PasswordService(get_settings())

    with pytest.raises(BadRequestException):
        service.hash_password("weak")
