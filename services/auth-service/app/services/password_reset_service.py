from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import randbelow

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AUDIT_PASSWORD_RESET_COMPLETED, AUDIT_PASSWORD_RESET_REQUESTED
from app.core.privacy import normalize_optional
from app.exceptions.auth import BadRequestException
from app.integrations.email.provider import EmailProvider
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.password_service import PasswordService
from app.services.session_service import SessionService


@dataclass(slots=True)
class PasswordResetRequestResult:
    email_sent: bool


class PasswordResetService:
    def __init__(
        self,
        *,
        settings: Settings,
        user_repository: UserRepository,
        password_service: PasswordService,
        password_reset_repository: PasswordResetRepository,
        refresh_token_repository: RefreshTokenRepository,
        session_service: SessionService,
        email_provider: EmailProvider,
        audit_service: AuditService,
    ) -> None:
        self.settings = settings
        self.user_repository = user_repository
        self.password_service = password_service
        self.password_reset_repository = password_reset_repository
        self.refresh_token_repository = refresh_token_repository
        self.session_service = session_service
        self.email_provider = email_provider
        self.audit_service = audit_service

    def _hash_token(self, raw_token: str) -> str:
        pepper = self.settings.password_reset_token_pepper_value.encode("utf-8")
        return hmac.new(pepper, raw_token.encode("utf-8"), sha256).hexdigest()

    def _generate_code(self) -> str:
        return f"{randbelow(1_000_000):06d}"

    async def request_reset(
        self,
        session: AsyncSession,
        *,
        email: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> PasswordResetRequestResult:
        normalized_email = email.lower()
        user = await self.user_repository.get_by_email(session, normalized_email)
        if user is None:
            return PasswordResetRequestResult(email_sent=False)

        code = self._generate_code()
        token_hash = self._hash_token(code)
        expires_at = datetime.now(tz=timezone.utc) + timedelta(
            seconds=self.settings.password_reset_token_ttl_value
        )

        await self.password_reset_repository.create(
            session,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            requested_ip=normalize_optional(ip_address),
            requested_user_agent=normalize_optional(user_agent),
        )

        await self.email_provider.send(
            to_email=user.email,
            subject="Reset your password",
            body=(
                "We received a request to reset your password.\n"
                f"Your reset code is: {code}\n\n"
                "If you did not request this, you can ignore this email."
            ),
        )

        await self.audit_service.log_event(
            session,
            event_type=AUDIT_PASSWORD_RESET_REQUESTED,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"email": user.email},
        )
        await session.commit()
        return PasswordResetRequestResult(email_sent=True)

    async def reset_password(
        self,
        session: AsyncSession,
        *,
        email: str,
        code: str,
        new_password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        normalized_email = email.lower()
        user = await self.user_repository.get_by_email(session, normalized_email)
        if user is None:
            raise BadRequestException("Invalid or expired reset code")

        token_hash = self._hash_token(code)
        record = await self.password_reset_repository.get_active_for_user_by_hash(
            session,
            user_id=user.id,
            token_hash=token_hash,
        )
        if record is None:
            raise BadRequestException("Invalid or expired reset code")
        if record.used_at is not None:
            raise BadRequestException("Reset code has already been used")
        now = datetime.now(tz=timezone.utc)
        if record.expires_at < now:
            raise BadRequestException("Reset code has expired")

        password_hash = self.password_service.hash_password(new_password)
        await self.user_repository.update_password(user, password_hash)
        await self.password_reset_repository.mark_used(record, now)

        await self.refresh_token_repository.revoke_all_for_user(session, user.id, reason="password_reset")
        await self.session_service.revoke_user_sessions(session, user.id)

        await self.audit_service.log_event(
            session,
            event_type=AUDIT_PASSWORD_RESET_COMPLETED,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await session.commit()
