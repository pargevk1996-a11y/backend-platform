from __future__ import annotations

import httpx
import pytest
from app.clients.auth_client import AuthClient
from app.clients.notification_client import NotificationClient
from app.clients.user_client import UserClient
from app.exceptions.gateway import RouteNotFoundException
from app.services.routing_service import RoutingService


@pytest.mark.asyncio
async def test_route_resolution() -> None:
    async with httpx.AsyncClient() as client:
        routing = RoutingService(
            auth_client=AuthClient(base_url="http://auth-service:8001", http_client=client),
            user_client=UserClient(base_url="http://user-service:8002", http_client=client),
            notification_client=NotificationClient(base_url=None, http_client=client),
        )

        assert routing.resolve_service("/v1/auth/login").__class__.__name__ == "AuthClient"
        assert routing.resolve_service("/v1/users/me").__class__.__name__ == "UserClient"

        with pytest.raises(RouteNotFoundException):
            routing.resolve_service("/v1/unknown/path")

        with pytest.raises(RouteNotFoundException):
            routing.resolve_service("/v1/notify/email")


@pytest.mark.asyncio
async def test_route_resolution_uses_strict_prefixes() -> None:
    async with httpx.AsyncClient() as client:
        routing = RoutingService(
            auth_client=AuthClient(base_url="http://auth-service:8001", http_client=client),
            user_client=UserClient(base_url="http://user-service:8002", http_client=client),
            notification_client=NotificationClient(base_url=None, http_client=client),
        )

        with pytest.raises(RouteNotFoundException):
            routing.resolve_service("/v1/authentication/login")

        with pytest.raises(RouteNotFoundException):
            routing.resolve_service("/v1/usersettings")


@pytest.mark.asyncio
async def test_notification_route_is_enabled_when_configured() -> None:
    async with httpx.AsyncClient() as client:
        routing = RoutingService(
            auth_client=AuthClient(base_url="http://auth-service:8001", http_client=client),
            user_client=UserClient(base_url="http://user-service:8002", http_client=client),
            notification_client=NotificationClient(
                base_url="http://notification:8003", http_client=client
            ),
        )

        assert (
            routing.resolve_service("/v1/notify/email").__class__.__name__ == "NotificationClient"
        )
