from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def init_engine(database_url: str) -> None:
    """Initialise the async engine with env-tunable pool parameters."""
    global _engine
    global _session_factory
    _engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=_int_env("DB_POOL_SIZE", 10),
        max_overflow=_int_env("DB_MAX_OVERFLOW", 5, minimum=0),
        pool_timeout=_int_env("DB_POOL_TIMEOUT", 5),
        pool_recycle=_int_env("DB_POOL_RECYCLE", 1800),
        connect_args={
            "server_settings": {"application_name": "user-service"},
            "timeout": _int_env("DB_CONNECT_TIMEOUT", 10),
        },
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory is not initialized")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory is not initialized")
    async with _session_factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine
    global _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
