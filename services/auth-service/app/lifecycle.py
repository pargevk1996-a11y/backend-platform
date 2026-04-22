from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, init_engine
from app.integrations.redis.client import close_redis_client, create_redis_client

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    smtp_ready = settings.smtp_is_configured
    LOGGER.info(
        "startup",
        extra={
            "email_smtp_configured": smtp_ready,
            "smtp_host_set": bool(settings.smtp_host),
            "smtp_from_set": bool(settings.smtp_from_email_value),
        },
    )
    init_engine(settings.database_url)

    redis = await create_redis_client(settings.redis_url)
    app.state.redis = redis

    try:
        yield
    finally:
        await close_redis_client(redis)
        await dispose_engine()
