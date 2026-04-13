from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    global _engine
    global _session_factory
    _engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=20,
        pool_recycle=1800,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


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
