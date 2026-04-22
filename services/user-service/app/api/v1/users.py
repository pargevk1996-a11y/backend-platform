from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_user_service_dep
from app.core.constants import PERMISSION_USERS_READ
from app.core.security import ensure_permission
from app.db.session import get_session
from app.schemas.users import UserMeResponse, UserResponse
from app.services.user_service import UserContext, UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeResponse)
async def me(context: UserContext = Depends(get_current_context)) -> UserMeResponse:
    return UserMeResponse(
        user_id=str(context.user.id),
        external_subject=context.user.external_subject,
        roles=context.roles,
        permissions=sorted(context.permissions),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    context: UserContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
    user_service: UserService = Depends(get_user_service_dep),
) -> UserResponse:
    ensure_permission(context.permissions, PERMISSION_USERS_READ)
    user = await user_service.get_user_by_id(session, user_id)
    return UserResponse(
        user_id=str(user.id),
        external_subject=user.external_subject,
        is_active=user.is_active,
    )
