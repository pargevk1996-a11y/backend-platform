from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_rbac_service
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine, get_session_factory, init_engine
from app.integrations.redis.client import close_redis_client, create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging()
    init_engine(settings.database_url)

    redis = await create_redis_client(settings.redis_url)
    app.state.redis = redis

    session_factory = get_session_factory()
    async with session_factory() as session:
        await get_rbac_service().ensure_seed_data(session)
        await session.commit()

    try:
        yield
    finally:
        await close_redis_client(redis)
        await dispose_engine()
