from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_current_session_info_exposes_two_factor_state() -> None:
    from app.api.v1.sessions import current_session_info

    user_id = uuid4()
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
    user = SimpleNamespace(
        id=user_id,
        email="user@example.com",
        two_factor_enabled=True,
    )

    response = await current_session_info(request, user)

    assert response.user_id == str(user_id)
    assert response.email == "user@example.com"
    assert response.client_ip == "127.0.0.1"
    assert response.two_factor_enabled is True
