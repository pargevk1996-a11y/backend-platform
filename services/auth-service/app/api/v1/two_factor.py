from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_audit_service,
    get_current_user,
    get_password_service,
    get_two_factor_service,
)
from app.core.config import get_settings
from app.core.constants import (
    AUDIT_2FA_DISABLED,
    AUDIT_2FA_ENABLED,
    AUDIT_2FA_SETUP_INITIATED,
    AUDIT_BACKUP_CODES_REGENERATED,
)
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_client_ip
from app.db.session import get_session
from app.exceptions.auth import InvalidCredentialsException
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.two_factor import (
    BackupCodesResponse,
    RegenerateBackupCodesRequest,
    TwoFactorDisableRequest,
    TwoFactorEnableRequest,
    TwoFactorSetupResponse,
)
from app.services.audit_service import AuditService
from app.services.password_service import PasswordService
from app.services.two_factor_service import TwoFactorService

router = APIRouter(prefix="/two-factor", tags=["two-factor"])
settings = get_settings()


def _mark_sensitive_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    audit_service: AuditService = Depends(get_audit_service),
    _: None = Depends(rate_limit_dependency("2fa_setup", settings.rate_limit_2fa_setup_per_minute)),
) -> TwoFactorSetupResponse:
    _mark_sensitive_response(response)
    setup_data = await two_factor_service.create_setup(session, user=current_user)
    await audit_service.log_event(
        session,
        event_type=AUDIT_2FA_SETUP_INITIATED,
        outcome="success",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return TwoFactorSetupResponse(
        qr_png_base64=setup_data.qr_png_base64,
        manual_entry_key=setup_data.secret,
    )


@router.post("/enable", response_model=BackupCodesResponse)
async def enable_two_factor(
    payload: TwoFactorEnableRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    audit_service: AuditService = Depends(get_audit_service),
    _: None = Depends(rate_limit_dependency("2fa_enable", settings.rate_limit_2fa_per_minute)),
) -> BackupCodesResponse:
    _mark_sensitive_response(response)
    backup_codes = await two_factor_service.enable(
        session,
        user=current_user,
        totp_code=payload.totp_code,
    )
    await audit_service.log_event(
        session,
        event_type=AUDIT_2FA_ENABLED,
        outcome="success",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return BackupCodesResponse(backup_codes=backup_codes.plain_codes)


@router.post("/disable", response_model=MessageResponse)
async def disable_two_factor(
    payload: TwoFactorDisableRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    password_service: PasswordService = Depends(get_password_service),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    audit_service: AuditService = Depends(get_audit_service),
    _: None = Depends(rate_limit_dependency("2fa_disable", settings.rate_limit_2fa_per_minute)),
) -> MessageResponse:
    if not password_service.verify_password(payload.password, current_user.password_hash):
        raise InvalidCredentialsException()

    await two_factor_service.disable(
        session,
        user=current_user,
        totp_code=payload.totp_code,
        backup_code=payload.backup_code,
    )
    await audit_service.log_event(
        session,
        event_type=AUDIT_2FA_DISABLED,
        outcome="success",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return MessageResponse(message="Two-factor authentication disabled")


@router.post("/backup-codes/regenerate", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    payload: RegenerateBackupCodesRequest,
    response: Response,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    two_factor_service: TwoFactorService = Depends(get_two_factor_service),
    audit_service: AuditService = Depends(get_audit_service),
    _: None = Depends(rate_limit_dependency("2fa_regenerate", settings.rate_limit_2fa_per_minute)),
) -> BackupCodesResponse:
    _mark_sensitive_response(response)
    generated = await two_factor_service.regenerate_backup_codes(
        session,
        user=current_user,
        totp_code=payload.totp_code,
        backup_code=payload.backup_code,
    )
    await audit_service.log_event(
        session,
        event_type=AUDIT_BACKUP_CODES_REGENERATED,
        outcome="success",
        actor_user_id=current_user.id,
        target_user_id=current_user.id,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return BackupCodesResponse(backup_codes=generated.plain_codes)
