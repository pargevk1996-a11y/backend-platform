from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.exceptions.auth import BadRequestException
from app.services.password_service import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordService,
)


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


@pytest.mark.asyncio
async def test_password_policy_rejects_below_min_length() -> None:
    service = PasswordService(get_settings())
    # 11 chars, 4 classes — long enough under the legacy `>=8` policy but below
    # the new minimum, so this pins the regression.
    too_short = "Aa1!Aa1!Aa1"
    assert len(too_short) == MIN_PASSWORD_LENGTH - 1

    with pytest.raises(BadRequestException, match="at least"):
        service.validate_password_policy(too_short)


@pytest.mark.asyncio
async def test_password_policy_rejects_above_max_length() -> None:
    service = PasswordService(get_settings())
    too_long = "Aa1!" * ((MAX_PASSWORD_LENGTH // 4) + 2)
    assert len(too_long) > MAX_PASSWORD_LENGTH

    with pytest.raises(BadRequestException, match="at most"):
        service.validate_password_policy(too_long)


@pytest.mark.asyncio
async def test_password_policy_rejects_insufficient_character_classes() -> None:
    service = PasswordService(get_settings())
    # 12 chars, only lower + digit = 2 classes -> must fail.
    two_classes = "aaaaaa111111"
    assert len(two_classes) >= MIN_PASSWORD_LENGTH

    with pytest.raises(BadRequestException, match="lowercase, uppercase"):
        service.validate_password_policy(two_classes)


@pytest.mark.asyncio
async def test_password_policy_accepts_three_classes_at_min_length() -> None:
    service = PasswordService(get_settings())
    # 12 chars, upper + lower + digit = 3 classes — boundary acceptance.
    exact = "Aaaaaaaaaa11"
    assert len(exact) == MIN_PASSWORD_LENGTH

    service.validate_password_policy(exact)  # must not raise
