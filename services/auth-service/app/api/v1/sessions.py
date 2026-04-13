from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.core.security import get_client_ip
from app.models.user import User

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/me")
async def current_session_info(request: Request, user: User = Depends(get_current_user)) -> dict[str, str]:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "client_ip": get_client_ip(request),
    }
