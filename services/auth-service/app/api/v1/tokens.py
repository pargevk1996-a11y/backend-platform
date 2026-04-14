from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_auth_service
from app.core.config import get_settings
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_client_ip
from app.db.session import get_session
from app.schemas.common import MessageResponse
from app.schemas.token import RefreshTokenRequest, RevokeTokenRequest, TokenPairResponse
from app.services.auth_service import AuthService

settings = get_settings()
router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    dependencies=[
        Depends(rate_limit_dependency("refresh", settings.rate_limit_refresh_per_minute))
    ],
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPairResponse:
    token_pair = await auth_service.refresh_tokens(
        session,
        refresh_token=payload.refresh_token,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return TokenPairResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.access_expires_in,
    )


@router.post("/revoke", response_model=MessageResponse)
async def revoke_token(
    payload: RevokeTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.revoke_refresh_token(
        session,
        refresh_token=payload.refresh_token,
        revoke_family=payload.revoke_family,
        ip_address=get_client_ip(request, trusted_proxy_ips=settings.trusted_proxy_ips),
        user_agent=request.headers.get("user-agent"),
    )
    return MessageResponse(message="Refresh token revoked")
