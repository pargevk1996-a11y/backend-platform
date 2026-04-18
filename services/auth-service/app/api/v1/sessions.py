from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import get_client_ip
from app.db.session import get_session
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.sessions import SessionInfoResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])
settings = get_settings()


@router.get("/me", response_model=SessionInfoResponse)
async def current_session_info(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> SessionInfoResponse:
    response = SessionInfoResponse(
        user_id=str(user.id),
        email=user.email,
        client_ip=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        two_factor_enabled=user.two_factor_enabled,
    )
    await session.commit()
    return response


@router.post("/touch", response_model=MessageResponse)
async def touch_current_session(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> MessageResponse:
    _ = user
    await session.commit()
    return MessageResponse(message="Session activity updated")
