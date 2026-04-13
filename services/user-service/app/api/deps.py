from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import AccessTokenService, extract_bearer_token, get_client_ip
from app.db.session import get_session
from app.exceptions.auth import UnauthorizedException
from app.integrations.redis.client import get_redis
from app.repositories.audit_repository import AuditRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.rbac_repository import RBACRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.rbac_service import RBACService
from app.services.user_service import UserContext, UserService


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    return UserRepository()


@lru_cache(maxsize=1)
def get_profile_repository() -> ProfileRepository:
    return ProfileRepository()


@lru_cache(maxsize=1)
def get_rbac_repository() -> RBACRepository:
    return RBACRepository()


@lru_cache(maxsize=1)
def get_audit_repository() -> AuditRepository:
    return AuditRepository()


@lru_cache(maxsize=1)
def get_rbac_service() -> RBACService:
    return RBACService(get_rbac_repository())


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    return AuditService(get_audit_repository())


@lru_cache(maxsize=1)
def get_user_service() -> UserService:
    return UserService(
        user_repository=get_user_repository(),
        profile_repository=get_profile_repository(),
        rbac_service=get_rbac_service(),
        audit_service=get_audit_service(),
    )


@lru_cache(maxsize=1)
def get_access_token_service() -> AccessTokenService:
    return AccessTokenService(get_settings())


def get_settings_dep() -> Settings:
    return get_settings()


async def get_current_context(
    request: Request,
    session: AsyncSession = Depends(get_session),
    token_service: AccessTokenService = Depends(get_access_token_service),
    user_service: UserService = Depends(get_user_service),
) -> UserContext:
    token = extract_bearer_token(request)
    claims = token_service.decode_access_token(token)

    context = await user_service.context_for_subject(
        session,
        subject=claims.sub,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    if not context.user.is_active:
        raise UnauthorizedException("Inactive user")

    if session.new or session.dirty:
        await session.commit()

    return context


async def get_user_service_dep() -> UserService:
    return get_user_service()


async def get_rbac_service_dep() -> RBACService:
    return get_rbac_service()


async def get_audit_service_dep() -> AuditService:
    return get_audit_service()


async def get_redis_dep(request: Request):
    return await get_redis(request)
