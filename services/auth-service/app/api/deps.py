from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.security import extract_bearer_token
from app.db.session import get_session
from app.exceptions.auth import UnauthorizedException
from app.integrations.redis.client import get_redis
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.two_factor_repository import TwoFactorRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.brute_force_protection_service import BruteForceProtectionService
from app.services.jwt_service import JWTService
from app.services.password_service import PasswordService
from app.services.refresh_token_service import RefreshTokenService
from app.services.session_service import SessionService
from app.services.two_factor_service import TwoFactorService


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    return UserRepository()


@lru_cache(maxsize=1)
def get_refresh_token_repository() -> RefreshTokenRepository:
    return RefreshTokenRepository()


@lru_cache(maxsize=1)
def get_two_factor_repository() -> TwoFactorRepository:
    return TwoFactorRepository()


@lru_cache(maxsize=1)
def get_session_repository() -> SessionRepository:
    return SessionRepository()


@lru_cache(maxsize=1)
def get_audit_repository() -> AuditRepository:
    return AuditRepository()


@lru_cache(maxsize=1)
def get_password_service() -> PasswordService:
    return PasswordService(get_settings())


@lru_cache(maxsize=1)
def get_jwt_service() -> JWTService:
    return JWTService(get_settings())


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    return SessionService(get_session_repository())


@lru_cache(maxsize=1)
def get_refresh_token_service() -> RefreshTokenService:
    return RefreshTokenService(
        settings=get_settings(),
        repository=get_refresh_token_repository(),
        jwt_service=get_jwt_service(),
        session_service=get_session_service(),
    )


@lru_cache(maxsize=1)
def get_two_factor_service() -> TwoFactorService:
    return TwoFactorService(
        settings=get_settings(),
        repository=get_two_factor_repository(),
        password_service=get_password_service(),
    )


@lru_cache(maxsize=1)
def get_audit_service() -> AuditService:
    return AuditService(get_audit_repository())


def get_settings_dep() -> Settings:
    return get_settings()


async def get_auth_service(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    user_repository: UserRepository = Depends(get_user_repository),
    password_service: PasswordService = Depends(get_password_service),
    refresh_token_service: RefreshTokenService = Depends(get_refresh_token_service),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuthService:
    redis = await get_redis(request)
    brute_force_service = BruteForceProtectionService(redis=redis, settings=settings)
    return AuthService(
        settings=settings,
        redis=redis,
        user_repository=user_repository,
        password_service=password_service,
        refresh_token_service=refresh_token_service,
        two_factor_service=two_factor_service,
        brute_force_service=brute_force_service,
        audit_service=audit_service,
    )


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    jwt_service: JWTService = Depends(get_jwt_service),
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    token = extract_bearer_token(request)
    claims = jwt_service.decode_and_validate(token, expected_type=TOKEN_TYPE_ACCESS)
    try:
        user_id = UUID(claims.sub)
    except ValueError as exc:
        raise UnauthorizedException("Invalid subject claim") from exc
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("User is inactive")
    return user
