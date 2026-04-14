from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_audit_service_dep,
    get_current_context,
    get_rbac_service_dep,
    get_user_service_dep,
)
from app.core.config import get_settings
from app.core.constants import AUDIT_ROLE_ASSIGNED, PERMISSION_ROLES_ASSIGN
from app.core.rate_limit import rate_limit_dependency
from app.core.security import ensure_permission, get_client_ip
from app.db.session import get_session
from app.schemas.common import MessageResponse
from app.schemas.roles import AssignRoleRequest, RolesResponse
from app.services.audit_service import AuditService
from app.services.rbac_service import RBACService
from app.services.user_service import UserContext, UserService

settings = get_settings()
router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/me", response_model=RolesResponse)
async def my_roles(context: UserContext = Depends(get_current_context)) -> RolesResponse:
    return RolesResponse(roles=context.roles)


@router.post(
    "/users/{user_id}",
    response_model=MessageResponse,
    dependencies=[
        Depends(
            rate_limit_dependency(
                "roles_write",
                settings.rate_limit_roles_write_per_minute,
            )
        )
    ],
)
async def assign_role(
    user_id: UUID,
    payload: AssignRoleRequest,
    request: Request,
    context: UserContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
    rbac_service: RBACService = Depends(get_rbac_service_dep),
    user_service: UserService = Depends(get_user_service_dep),
    audit_service: AuditService = Depends(get_audit_service_dep),
) -> MessageResponse:
    ensure_permission(context.permissions, PERMISSION_ROLES_ASSIGN)
    await user_service.get_user_by_id(session, user_id)
    await rbac_service.assign_role_by_name(
        session,
        user_id=user_id,
        role_name=payload.role_name,
    )
    await audit_service.log_event(
        session,
        event_type=AUDIT_ROLE_ASSIGNED,
        outcome="success",
        actor_user_id=context.user.id,
        target_user_id=user_id,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
        payload={"role_name": payload.role_name},
    )
    await session.commit()
    return MessageResponse(message="Role assigned")
