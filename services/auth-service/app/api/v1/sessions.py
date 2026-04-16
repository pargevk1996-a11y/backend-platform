from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.sessions import SessionInfoResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])
settings = get_settings()


@router.get("/me", response_model=SessionInfoResponse)
async def current_session_info(
    request: Request, user: User = Depends(get_current_user)
) -> SessionInfoResponse:
    return SessionInfoResponse(
        user_id=str(user.id),
        email=user.email,
        client_ip=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        two_factor_enabled=user.two_factor_enabled,
    )
