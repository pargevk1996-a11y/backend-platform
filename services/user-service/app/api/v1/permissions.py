from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_context
from app.schemas.permissions import PermissionsResponse
from app.services.user_service import UserContext

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me", response_model=PermissionsResponse)
async def my_permissions(context: UserContext = Depends(get_current_context)) -> PermissionsResponse:
    return PermissionsResponse(permissions=sorted(context.permissions))
