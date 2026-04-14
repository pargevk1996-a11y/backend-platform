from __future__ import annotations

import pytest
from app.core.security import ensure_permission
from app.exceptions.auth import ForbiddenException


@pytest.mark.asyncio
async def test_ensure_permission_rejects_missing_permission() -> None:
    with pytest.raises(ForbiddenException):
        ensure_permission({"profile:read:self"}, "roles:assign")
