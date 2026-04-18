from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import TOKEN_TYPE_REFRESH
from app.exceptions.token import InvalidTokenException, TokenReuseDetectedException
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.services.jwt_service import JWTService
from app.services.session_service import SessionService


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_family_id: UUID
    session_id: UUID


@dataclass(slots=True)
class RefreshRevocationResult:
    family_id: UUID
    session_id: UUID


class RefreshTokenService:
    """Refresh-token rotation and revocation with reuse detection."""

    def __init__(
        self,
        *,
        settings: Settings,
        repository: RefreshTokenRepository,
        jwt_service: JWTService,
        session_service: SessionService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.jwt_service = jwt_service
        self.session_service = session_service

    def _hash_refresh_token(self, raw_token: str) -> str:
        pepper = self.settings.refresh_token_hash_pepper_value.encode("utf-8")
        digest = hmac.new(pepper, raw_token.encode("utf-8"), sha256).hexdigest()
        return digest

    async def issue_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        family_id = uuid4()
        user_session = await self.session_service.create_session(
            session,
            user_id=user_id,
            refresh_family_id=family_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        refresh_jti = self.jwt_service.generate_jti()
        refresh_token, refresh_exp = self.jwt_service.issue_refresh_token(
            subject=user_id,
            session_id=user_session.id,
            family_id=family_id,
            jti=refresh_jti,
        )
        await self.repository.create(
            session,
            user_id=user_id,
            jti=refresh_jti,
            family_id=family_id,
            parent_jti=None,
            token_hash=self._hash_refresh_token(refresh_token),
            expires_at=refresh_exp,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        access_token, access_expires_in = self.jwt_service.issue_access_token(
            subject=user_id,
            session_id=user_session.id,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in=access_expires_in,
            refresh_family_id=family_id,
            session_id=user_session.id,
        )

    async def rotate(
        self,
        session: AsyncSession,
        *,
        raw_refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        claims = self.jwt_service.decode_and_validate(
            raw_refresh_token,
            expected_type=TOKEN_TYPE_REFRESH,
        )
        if claims.family_id is None or claims.session_id is None:
            raise InvalidTokenException("Missing required refresh token claims")

        try:
            token_jti = UUID(claims.jti)
            family_id = UUID(claims.family_id)
            session_id = UUID(claims.session_id)
            user_id = UUID(claims.sub)
        except ValueError as exc:
            raise InvalidTokenException("Malformed UUID claim in token") from exc

        token_record = await self.repository.get_by_jti_for_update(session, token_jti)
        if token_record is None:
            raise InvalidTokenException()

        if token_record.user_id != user_id or token_record.family_id != family_id:
            raise InvalidTokenException("Refresh token claims do not match persisted token")

        expected_hash = self._hash_refresh_token(raw_refresh_token)
        if not hmac.compare_digest(token_record.token_hash, expected_hash):
            raise InvalidTokenException()

        family_active = await self.session_service.is_family_active(session, family_id)
        if not family_active:
            raise InvalidTokenException("Session is revoked")

        now = datetime.now(tz=UTC)
        if token_record.expires_at < now:
            raise InvalidTokenException("Refresh token expired")

        active_session = await self.session_service.touch_session_activity(
            session,
            session_id=session_id,
            idle_timeout_seconds=self.settings.session_idle_timeout_seconds,
        )
        if active_session is None:
            raise InvalidTokenException("Session expired due to inactivity")

        if token_record.revoked_at is not None or token_record.rotated_at is not None:
            await self.repository.revoke_family(session, family_id, "reuse_detected")
            await self.session_service.revoke_family(session, family_id)
            raise TokenReuseDetectedException(session_id=session_id, family_id=family_id)

        new_jti = uuid4()
        new_refresh_token, new_refresh_exp = self.jwt_service.issue_refresh_token(
            subject=user_id,
            session_id=session_id,
            family_id=family_id,
            jti=new_jti,
        )

        await self.repository.mark_rotated(session, token=token_record, replaced_by_jti=new_jti)
        await self.repository.create(
            session,
            user_id=user_id,
            jti=new_jti,
            family_id=family_id,
            parent_jti=token_record.jti,
            token_hash=self._hash_refresh_token(new_refresh_token),
            expires_at=new_refresh_exp,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.session_service.touch_family(session, family_id)

        access_token, access_expires_in = self.jwt_service.issue_access_token(
            subject=user_id,
            session_id=session_id,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh_token,
            access_expires_in=access_expires_in,
            refresh_family_id=family_id,
            session_id=session_id,
        )

    async def revoke(
        self,
        session: AsyncSession,
        *,
        raw_refresh_token: str,
        revoke_family: bool,
        reason: str,
    ) -> RefreshRevocationResult | None:
        claims = self.jwt_service.decode_and_validate(
            raw_refresh_token,
            expected_type=TOKEN_TYPE_REFRESH,
        )
        if claims.family_id is None or claims.session_id is None:
            raise InvalidTokenException("Missing required refresh token claims")

        try:
            token_jti = UUID(claims.jti)
            family_id = UUID(claims.family_id)
            session_id = UUID(claims.session_id)
            user_id = UUID(claims.sub)
        except ValueError as exc:
            raise InvalidTokenException("Malformed UUID claim in token") from exc

        token_record = await self.repository.get_by_jti_for_update(session, token_jti)
        if token_record is None:
            return None

        expected_hash = self._hash_refresh_token(raw_refresh_token)
        if not hmac.compare_digest(token_record.token_hash, expected_hash):
            raise InvalidTokenException()

        if token_record.family_id != family_id:
            raise InvalidTokenException("Refresh token family mismatch")
        if token_record.user_id != user_id:
            raise InvalidTokenException("Refresh token subject mismatch")

        if revoke_family:
            await self.repository.revoke_family(session, family_id, reason)
            await self.session_service.revoke_family(session, family_id)
            return RefreshRevocationResult(family_id=family_id, session_id=session_id)

        await self.repository.revoke_token(session, token=token_record, reason=reason)
        return RefreshRevocationResult(family_id=family_id, session_id=session_id)
