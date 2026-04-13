from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, Request
from fastapi import HTTPException

from app.db.session import get_session
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    await session.execute(text("SELECT 1"))
    result = await session.execute(text("SELECT to_regclass('public.alembic_version')"))
    if result.scalar_one() is None:
        raise HTTPException(status_code=503, detail="Database migrations not applied")
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not initialized")
    await redis.ping()
    return HealthResponse(status="ok")
