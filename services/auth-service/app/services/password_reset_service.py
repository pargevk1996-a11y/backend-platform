from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import randbelow
from uuid import UUID

from redis.asyncio import Redis
from smtplib import SMTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AUDIT_PASSWORD_RESET_COMPLETED, AUDIT_PASSWORD_RESET_REQUESTED
from app.core.privacy import normalize_optional
from app.exceptions.auth import (
    BadRequestException,
    PasswordResetFlowBlockedException,
    ServiceUnavailableException,
    UnknownUserPasswordResetException,
)
from app.models.user import User
from app.integrations.email.provider import EmailProvider
from app.integrations.redis.keys import access_session_revoked_key
from app.repositories.password_reset_repository import PasswordResetRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.brute_force_protection_service import BruteForceProtectionService
from app.services.password_service import PasswordService
from app.services.session_service import SessionService

LOGGER = logging.getLogger(__name__)


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
        redis: Redis,
        email_provider: EmailProvider,
        audit_service: AuditService,
        brute_force_service: BruteForceProtectionService,
    ) -> None:
        self.settings = settings
        self.user_repository = user_repository
        self.password_service = password_service
        self.password_reset_repository = password_reset_repository
        self.refresh_token_repository = refresh_token_repository
        self.session_service = session_service
        self.redis = redis
        self.email_provider = email_provider
        self.audit_service = audit_service
        self.brute_force_service = brute_force_service

    def _hash_token(self, raw_token: str) -> str:
        pepper = self.settings.password_reset_token_pepper_value.encode("utf-8")
        return hmac.new(pepper, raw_token.encode("utf-8"), sha256).hexdigest()

    def _generate_code(self) -> str:
        return f"{randbelow(1_000_000):06d}"

    async def _mark_access_sessions_revoked(self, session_ids: list[UUID]) -> None:
        for session_id in session_ids:
            await self.redis.set(
                access_session_revoked_key(str(session_id)),
                "1",
                ex=max(self.settings.jwt_access_ttl_seconds, 60),
            )

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
            raise UnknownUserPasswordResetException()
        if user.password_reset_blocked:
            raise PasswordResetFlowBlockedException(self.settings.password_reset_flow_blocked_message)

        if not self.settings.smtp_is_configured:
            if self.settings.auth_allow_missing_smtp:
                return PasswordResetRequestResult(email_sent=False)
            raise ServiceUnavailableException(
                "Password reset email is not configured. Contact the administrator."
            )

        code = self._generate_code()
        token_hash = self._hash_token(code)
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(seconds=self.settings.password_reset_token_ttl_value)

        await self.password_reset_repository.mark_active_for_user_used(
            session,
            user_id=user.id,
            used_at=now,
        )
        await self.password_reset_repository.create(
            session,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            requested_ip=normalize_optional(ip_address),
            requested_user_agent=normalize_optional(user_agent),
        )

        subject = "Password reset code"
        body = f"Your 6-digit password reset code is: {code}\n"
        try:
            sent = await self.email_provider.send(
                to_email=user.email,
                subject=subject,
                body=body,
            )
            if sent is not True:
                await session.rollback()
                raise ServiceUnavailableException(
                    "Unable to send password reset email. Check SMTP settings or try again later."
                )
        except (SMTPException, OSError, RuntimeError) as exc:
            await session.rollback()
            LOGGER.exception(
                "password_reset.email_send_failed",
                extra={
                    "user_id": str(user.id),
                    "smtp_host": self.settings.smtp_host,
                    "smtp_port": self.settings.smtp_port,
                },
            )
            raise ServiceUnavailableException(
                "Unable to send password reset email. Check SMTP settings or try again later."
            ) from exc
        except Exception as exc:
            await session.rollback()
            LOGGER.exception(
                "password_reset.email_send_unexpected",
                extra={
                    "user_id": str(user.id),
                    "smtp_host": self.settings.smtp_host,
                    "smtp_port": self.settings.smtp_port,
                },
            )
            raise ServiceUnavailableException(
                "Unable to send password reset email. Check SMTP settings or try again later."
            ) from exc

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
        identifier = f"{normalized_email}:{ip_address or 'unknown'}"
        account_identifier = normalized_email
        await self.brute_force_service.assert_not_locked(
            scope="password_reset",
            identifier=identifier,
        )
        await self.brute_force_service.assert_not_locked(
            scope="password_reset_account",
            identifier=account_identifier,
        )

        user = await self.user_repository.get_by_email(session, normalized_email)
        if user is None:
            await self._record_reset_failure(session, identifier, account_identifier, user=None)
            raise BadRequestException("Invalid or expired reset code")
        if user.password_reset_blocked:
            raise PasswordResetFlowBlockedException(self.settings.password_reset_flow_blocked_message)

        token_hash = self._hash_token(code)
        record = await self.password_reset_repository.get_active_for_user_by_hash(
            session,
            user_id=user.id,
            token_hash=token_hash,
        )
        if record is None:
            await self._record_reset_failure(session, identifier, account_identifier, user=user)
            raise BadRequestException("Invalid or expired reset code")
        if record.used_at is not None:
            await self._record_reset_failure(session, identifier, account_identifier, user=user)
            raise BadRequestException("Invalid or expired reset code")
        now = datetime.now(tz=UTC)
        if record.expires_at < now:
            await self._record_reset_failure(session, identifier, account_identifier, user=user)
            raise BadRequestException("Invalid or expired reset code")

        password_hash = self.password_service.hash_password(new_password)
        await self.user_repository.update_password(user, password_hash)
        await self.password_reset_repository.mark_used(record, now)

        active_session_ids = await self.session_service.list_active_session_ids_for_user(
            session, user.id
        )
        await self.refresh_token_repository.revoke_all_for_user(
            session, user.id, reason="password_reset"
        )
        await self.session_service.revoke_user_sessions(session, user.id)
        await self._mark_access_sessions_revoked(active_session_ids)
        await self.brute_force_service.clear_failures(
            scope="password_reset",
            identifier=identifier,
        )
        await self.brute_force_service.clear_failures(
            scope="password_reset_account",
            identifier=account_identifier,
        )

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

    async def _record_reset_failure(
        self,
        session: AsyncSession,
        identifier: str,
        account_identifier: str,
        *,
        user: User | None,
    ) -> None:
        await self.brute_force_service.record_failure(
            scope="password_reset",
            identifier=identifier,
        )
        acct_attempts = await self.brute_force_service.record_failure(
            scope="password_reset_account",
            identifier=account_identifier,
        )
        if user is not None and acct_attempts >= self.settings.brute_force_password_reset_max_attempts:
            user.password_reset_blocked = True
            await session.flush()
            # Persist before raising BadRequest: session middleware rolls back uncommitted work.
            await session.commit()
