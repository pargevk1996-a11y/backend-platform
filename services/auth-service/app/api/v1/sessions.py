from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import get_client_ip
from app.models.user import User
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])
settings = get_settings()


@router.get("/me")
async def current_session_info(
    request: Request, user: User = Depends(get_current_user)
) -> dict[str, str]:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "client_ip": get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
    }


@router.post("/touch", response_model=MessageResponse)
async def touch_current_session(user: User = Depends(get_current_user)) -> MessageResponse:
    _ = user
    return MessageResponse(message="Session activity updated")
