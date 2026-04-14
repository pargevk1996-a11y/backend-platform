from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.config import get_settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.exceptions.token import InvalidTokenException
from app.services.jwt_service import JWTService


@pytest.mark.asyncio
async def test_issue_and_decode_access_token() -> None:
    service = JWTService(get_settings())

    token, _ = service.issue_access_token(subject=uuid4(), session_id=uuid4())
    claims = service.decode_and_validate(token, expected_type=TOKEN_TYPE_ACCESS)

    assert claims.token_type == TOKEN_TYPE_ACCESS
    assert claims.sub
    assert claims.jti


@pytest.mark.asyncio
async def test_reject_wrong_expected_type() -> None:
    service = JWTService(get_settings())
    token, _ = service.issue_access_token(subject=uuid4(), session_id=uuid4())

    with pytest.raises(InvalidTokenException):
        service.decode_and_validate(token, expected_type="refresh")
