from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service, get_password_reset_service
from app.core.config import get_settings
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_client_ip
from app.db.session import get_session
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LoginTwoFactorRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    RegisterRequest,
)
from app.schemas.token import TokenPairResponse
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(rate_limit_dependency("register", "rate_limit_register_per_minute"))
    ],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    token_pair = await auth_service.register(
        session,
        email=payload.email,
        password=payload.password,
        ip_address=get_client_ip(request, trusted_proxy_ips=get_settings().trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.access_expires_in,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(rate_limit_dependency("login", "rate_limit_login_per_minute"))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    result = await auth_service.login(
        session,
        email=payload.email,
        password=payload.password,
        ip_address=get_client_ip(request, trusted_proxy_ips=get_settings().trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )

    if result.requires_2fa:
        return LoginResponse(requires_2fa=True, challenge_id=result.challenge_id)

    tokens = result.tokens
    if tokens is None:
        # This branch should be unreachable: when requires_2fa is False the
        # auth service always returns tokens. Log loudly so it shows up in
        # incident dashboards if the invariant ever breaks.
        LOGGER.error(
            "auth.login_invariant_violation",
            extra={"invariant": "tokens_missing_without_2fa"},
        )
        raise RuntimeError("Unexpected login state: token pair is missing without 2FA")
    return LoginResponse(
        requires_2fa=False,
        tokens=TokenPairResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_in=tokens.access_expires_in,
        ),
    )


@router.post(
    "/login/2fa",
    response_model=TokenPairResponse,
    dependencies=[Depends(rate_limit_dependency("2fa", "rate_limit_2fa_per_minute"))],
)
async def verify_login_2fa(
    payload: LoginTwoFactorRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    token_pair = await auth_service.verify_login_challenge(
        session,
        challenge_id=payload.challenge_id,
        totp_code=payload.totp_code,
        backup_code=payload.backup_code,
        ip_address=get_client_ip(request, trusted_proxy_ips=get_settings().trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.access_expires_in,
    )


@router.post(
    "/password/forgot",
    response_model=PasswordResetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(
            rate_limit_dependency("password_reset", "rate_limit_password_reset_per_minute")
        )
    ],
)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    reset_service: PasswordResetService = Depends(get_password_reset_service),
) -> PasswordResetResponse:
    await reset_service.request_reset(
        session,
        email=payload.email,
        ip_address=get_client_ip(request, trusted_proxy_ips=get_settings().trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return PasswordResetResponse()


@router.post(
    "/password/reset",
    response_model=PasswordResetResponse,
    dependencies=[
        Depends(
            rate_limit_dependency(
                "password_reset_confirm",
                "rate_limit_password_reset_per_minute",
            )
        )
    ],
)
async def reset_password(
    payload: PasswordResetConfirmRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    reset_service: PasswordResetService = Depends(get_password_reset_service),
) -> PasswordResetResponse:
    await reset_service.reset_password(
        session,
        email=payload.email,
        code=payload.code,
        new_password=payload.password,
        ip_address=get_client_ip(request, trusted_proxy_ips=get_settings().trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return PasswordResetResponse()
