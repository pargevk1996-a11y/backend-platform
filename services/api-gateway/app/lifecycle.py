from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.clients.auth_client import AuthClient
from app.clients.notification_client import NotificationClient
from app.clients.user_client import UserClient
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.integrations.redis.client import close_redis_client, create_redis_client
from app.services.routing_service import RoutingService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings

    configure_logging()

    redis = await create_redis_client(settings.redis_url)
    app.state.redis = redis

    timeout = httpx.Timeout(settings.upstream_timeout_seconds)
    http_client = httpx.AsyncClient(timeout=timeout)
    app.state.http_client = http_client

    auth_client = AuthClient(base_url=settings.auth_service_url, http_client=http_client)
    user_client = UserClient(base_url=settings.user_service_url, http_client=http_client)
    notification_client = NotificationClient(
        base_url=settings.notification_service_url,
        http_client=http_client,
    )

    app.state.routing_service = RoutingService(
        auth_client=auth_client,
        user_client=user_client,
        notification_client=notification_client,
    )

    try:
        yield
    finally:
        await http_client.aclose()
        await close_redis_client(redis)
