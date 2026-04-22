from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_context, get_user_service_dep
from app.core.config import get_settings
from app.core.constants import PERMISSION_PROFILE_READ_SELF, PERMISSION_PROFILE_WRITE_SELF
from app.core.rate_limit import rate_limit_dependency
from app.core.security import ensure_permission, get_client_ip
from app.db.session import get_session
from app.schemas.profiles import ProfileResponse, UpdateProfileRequest
from app.services.user_service import UserContext, UserService

settings = get_settings()
router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
async def my_profile(context: UserContext = Depends(get_current_context)) -> ProfileResponse:
    ensure_permission(context.permissions, PERMISSION_PROFILE_READ_SELF)
    return ProfileResponse(
        user_id=str(context.user.id),
        display_name=context.profile.display_name,
        locale=context.profile.locale,
        timezone=context.profile.timezone,
        avatar_url=context.profile.avatar_url,
    )


@router.patch(
    "/me",
    response_model=ProfileResponse,
    dependencies=[
        Depends(
            rate_limit_dependency(
                "profile_write",
                settings.rate_limit_profile_write_per_minute,
            )
        )
    ],
)
async def update_profile(
    payload: UpdateProfileRequest,
    request: Request,
    context: UserContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
    user_service: UserService = Depends(get_user_service_dep),
) -> ProfileResponse:
    ensure_permission(context.permissions, PERMISSION_PROFILE_WRITE_SELF)

    updated = await user_service.update_own_profile(
        session,
        user_id=context.user.id,
        actor_user_id=context.user.id,
        display_name=payload.display_name,
        locale=payload.locale,
        timezone=payload.timezone,
        avatar_url=payload.avatar_url,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()

    return ProfileResponse(
        user_id=str(updated.user_id),
        display_name=updated.display_name,
        locale=updated.locale,
        timezone=updated.timezone,
        avatar_url=updated.avatar_url,
    )
