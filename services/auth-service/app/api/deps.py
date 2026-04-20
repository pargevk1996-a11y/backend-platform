from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.core.security import ensure_access_session_active, extract_bearer_token
from app.db.session import get_session
from app.exceptions.auth import UnauthorizedException
from app.integrations.email.provider import EmailProvider
from app.integrations.redis.client import get_redis
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.two_factor_repository import TwoFactorRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.brute_force_protection_service import BruteForceProtectionService
from app.services.jwt_service import JWTService
from app.services.password_reset_service import PasswordResetService
from app.services.password_service import PasswordService
from app.services.refresh_token_service import RefreshTokenService
from app.services.session_service import SessionService
from app.services.two_factor_service import TwoFactorService


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_refresh_token_repository() -> RefreshTokenRepository:
    return RefreshTokenRepository()


def get_password_reset_repository() -> PasswordResetRepository:
    return PasswordResetRepository()


def get_two_factor_repository() -> TwoFactorRepository:
    return TwoFactorRepository()


def get_session_repository() -> SessionRepository:
    return SessionRepository()


def get_audit_repository() -> AuditRepository:
    return AuditRepository()


@lru_cache(maxsize=1)
def get_password_service() -> PasswordService:
    return PasswordService(get_settings())


@lru_cache(maxsize=1)
def get_jwt_service() -> JWTService:
    return JWTService(get_settings())


def get_session_service() -> SessionService:
    return SessionService(get_session_repository())


def get_refresh_token_service() -> RefreshTokenService:
    return RefreshTokenService(
        settings=get_settings(),
        repository=get_refresh_token_repository(),
        jwt_service=get_jwt_service(),
        session_service=get_session_service(),
    )


def get_two_factor_service() -> TwoFactorService:
    return TwoFactorService(
        settings=get_settings(),
        repository=get_two_factor_repository(),
        password_service=get_password_service(),
    )


def get_audit_service() -> AuditService:
    return AuditService(get_audit_repository())


def get_email_provider() -> EmailProvider:
    """Build per request: avoid stale SMTP credentials if process env/settings change."""
    settings = get_settings()
    return EmailProvider(
        host=getattr(settings, "smtp_host", None),
        port=getattr(settings, "smtp_port", 587),
        username=getattr(settings, "smtp_username", None),
        password=settings.smtp_password_value,
        use_tls=getattr(settings, "smtp_use_tls", True),
        from_email=settings.smtp_from_email_value,
        from_name=settings.smtp_from_name,
        require_delivery=settings.smtp_require_delivery_value,
    )


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


async def get_password_reset_service(
    request: Request,
    settings: Settings = Depends(get_settings_dep),
    user_repository: UserRepository = Depends(get_user_repository),
    password_service: PasswordService = Depends(get_password_service),
    reset_repository: PasswordResetRepository = Depends(get_password_reset_repository),
    refresh_token_repository: RefreshTokenRepository = Depends(get_refresh_token_repository),
    session_service: SessionService = Depends(get_session_service),
    email_provider: EmailProvider = Depends(get_email_provider),
    audit_service: AuditService = Depends(get_audit_service),
) -> PasswordResetService:
    redis = await get_redis(request)
    brute_force_service = BruteForceProtectionService(redis=redis, settings=settings)
    return PasswordResetService(
        settings=settings,
        user_repository=user_repository,
        password_service=password_service,
        password_reset_repository=reset_repository,
        refresh_token_repository=refresh_token_repository,
        session_service=session_service,
        redis=redis,
        email_provider=email_provider,
        audit_service=audit_service,
        brute_force_service=brute_force_service,
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
        if claims.session_id is None:
            raise ValueError
        session_id = UUID(claims.session_id)
    except ValueError as exc:
        raise UnauthorizedException("Invalid access token claims") from exc
    redis = await get_redis(request)
    await ensure_access_session_active(redis, session_id)
    user = await user_repository.get_by_id(session, user_id)
    if user is None:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("User is inactive")
    return user
