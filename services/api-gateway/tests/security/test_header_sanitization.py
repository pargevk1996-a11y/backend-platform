from __future__ import annotations

import httpx
import pytest

from app.clients.auth_client import AuthClient
from app.clients.notification_client import NotificationClient
from app.clients.user_client import UserClient
from app.services.routing_service import RoutingService


@pytest.mark.asyncio
async def test_hop_by_hop_headers_are_removed() -> None:
    async with httpx.AsyncClient() as client:
        service = RoutingService(
            auth_client=AuthClient(base_url="http://auth", http_client=client),
            user_client=UserClient(base_url="http://user", http_client=client),
            notification_client=NotificationClient(base_url=None, http_client=client),
        )

        sanitized = service._sanitize_request_headers(
            {
                "Host": "example.com",
                "Connection": "keep-alive",
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            }
        )

        assert "Authorization" in sanitized
        assert "Content-Type" in sanitized
        assert "Host" not in sanitized
        assert "Connection" not in sanitized
