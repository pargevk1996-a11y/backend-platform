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
                "X-Forwarded-For": "203.0.113.10",
                "X-Real-IP": "203.0.113.11",
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Request-ID": "req-1",
                "X-CSRF-Token": "csrf",
                "Cookie": "bad=1",
            }
        )

        assert "Authorization" in sanitized
        assert "Content-Type" in sanitized
        assert "Accept" in sanitized
        assert "X-Request-ID" in sanitized
        assert "X-CSRF-Token" in sanitized
        assert "Host" not in sanitized
        assert "Connection" not in sanitized
        assert "X-Forwarded-For" not in sanitized
        assert "X-Real-IP" not in sanitized
        assert "Cookie" not in sanitized


@pytest.mark.asyncio
async def test_sensitive_response_headers_are_removed() -> None:
    async with httpx.AsyncClient() as client:
        service = RoutingService(
            auth_client=AuthClient(base_url="http://auth", http_client=client),
            user_client=UserClient(base_url="http://user", http_client=client),
            notification_client=NotificationClient(base_url=None, http_client=client),
        )

        sanitized = service._sanitize_response_headers(
            httpx.Headers(
                {
                    "Set-Cookie": "session=attacker",
                    "Server": "upstream",
                    "X-Powered-By": "framework",
                    "Content-Type": "application/json",
                }
            )
        )

        assert "content-type" in sanitized
        assert "set-cookie" not in sanitized
        assert "server" not in sanitized
        assert "x-powered-by" not in sanitized
