from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import (
    AUDIT_LOGIN_FAILED,
    AUDIT_LOGIN_SUCCESS,
    AUDIT_REFRESH_REUSE_DETECTED,
    AUDIT_REFRESH_REVOKED,
    AUDIT_REFRESH_SUCCESS,
    AUDIT_REGISTER_SUCCESS,
)
from app.core.privacy import normalize_optional, stable_hmac_digest
from app.exceptions.auth import (
    AccountLoginBlockedException,
    InvalidCredentialsException,
    UserAlreadyExistsException,
)
from app.exceptions.token import InvalidTokenException, TokenReuseDetectedException
from app.exceptions.two_factor import InvalidChallengeException, InvalidTwoFactorCodeException
from app.integrations.redis.keys import access_session_revoked_key, login_challenge_key
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.brute_force_protection_service import BruteForceProtectionService
from app.services.password_service import PasswordService
from app.services.refresh_token_service import RefreshTokenService, TokenPair
from app.services.two_factor_service import TwoFactorService


@dataclass(slots=True)
class LoginStepResult:
    requires_2fa: bool
    challenge_id: str | None
    tokens: TokenPair | None


class AuthService:
    """Core authentication orchestration service."""

    def __init__(
        self,
        *,
        settings: Settings,
        redis: Redis,
        user_repository: UserRepository,
        password_service: PasswordService,
        refresh_token_service: RefreshTokenService,
        two_factor_service: TwoFactorService,
        brute_force_service: BruteForceProtectionService,
        audit_service: AuditService,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.user_repository = user_repository
        self.password_service = password_service
        self.refresh_token_service = refresh_token_service
        self.two_factor_service = two_factor_service
        self.brute_force_service = brute_force_service
        self.audit_service = audit_service

    async def register(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        existing = await self.user_repository.get_by_email(session, email)
        if existing is not None:
            raise UserAlreadyExistsException()

        password_hash = self.password_service.hash_password(password)
        user = await self.user_repository.create(session, email=email, password_hash=password_hash)
        token_pair = await self.refresh_token_service.issue_for_user(
            session,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.audit_service.log_event(
            session,
            event_type=AUDIT_REGISTER_SUCCESS,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"email": user.email},
        )
        await session.commit()
        return token_pair

    async def login(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> LoginStepResult:
        normalized_email = email.lower()
        identifier = f"{normalized_email}:{ip_address or 'unknown'}"

        user = await self.user_repository.get_by_email(session, normalized_email)
        if user is not None and user.login_blocked:
            raise AccountLoginBlockedException(self.settings.account_login_locked_message)

        await self.brute_force_service.assert_not_locked(scope="login", identifier=identifier)

        if user is not None:
            await self.brute_force_service.assert_not_locked(
                scope="login_account", identifier=normalized_email
            )

        if user is None:
            self.password_service.verify_against_dummy_hash(password)
            password_ok = False
        else:
            password_ok = self.password_service.verify_password(password, user.password_hash)
        if not password_ok:
            await self.brute_force_service.record_failure(scope="login", identifier=identifier)
            if user is not None:
                acct_attempts = await self.brute_force_service.record_failure(
                    scope="login_account", identifier=normalized_email
                )
                if acct_attempts >= self.settings.brute_force_login_max_attempts:
                    user.login_blocked = True
                    await session.flush()
                    # #region agent log
                    try:
                        import json
                        import time

                        with open(
                            "/home/pash666/backend-platform/.cursor/debug-b7feee.log",
                            "a",
                            encoding="utf-8",
                        ) as _lf:
                            _lf.write(
                                json.dumps(
                                    {
                                        "sessionId": "b7feee",
                                        "hypothesisId": "H1",
                                        "location": "auth_service.py:login",
                                        "message": "login_account_locked_after_attempts",
                                        "data": {
                                            "acct_attempts": acct_attempts,
                                            "max": self.settings.brute_force_login_max_attempts,
                                        },
                                        "timestamp": int(time.time() * 1000),
                                    }
                                )
                                + "\n"
                            )
                    except Exception:
                        pass
                    # #endregion
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_LOGIN_FAILED,
                outcome="failure",
                actor_user_id=user.id if user else None,
                target_user_id=user.id if user else None,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"email": normalized_email},
            )
            await session.commit()
            raise InvalidCredentialsException()

        if user is None:
            raise RuntimeError("Unexpected login state: password verified without a user")

        if not user.is_active:
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_LOGIN_FAILED,
                outcome="failure",
                actor_user_id=user.id,
                target_user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"email": normalized_email, "reason": "inactive_account"},
            )
            await session.commit()
            raise InvalidCredentialsException()

        await self.brute_force_service.clear_failures(scope="login", identifier=identifier)
        await self.brute_force_service.clear_failures(
            scope="login_account", identifier=normalized_email
        )

        if user.two_factor_enabled:
            challenge_id = await self._create_login_challenge(
                user_id=user.id,
                ip_address=ip_address,
            )
            return LoginStepResult(requires_2fa=True, challenge_id=challenge_id, tokens=None)

        token_pair = await self.refresh_token_service.issue_for_user(
            session,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.audit_service.log_event(
            session,
            event_type=AUDIT_LOGIN_SUCCESS,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await session.commit()

        return LoginStepResult(requires_2fa=False, challenge_id=None, tokens=token_pair)

    async def verify_login_challenge(
        self,
        session: AsyncSession,
        *,
        challenge_id: str,
        totp_code: str | None,
        backup_code: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        identifier = f"{challenge_id}:{ip_address or 'unknown'}"
        await self.brute_force_service.assert_not_locked(scope="2fa", identifier=identifier)

        challenge = await self._get_login_challenge(challenge_id)
        if challenge is None:
            raise InvalidChallengeException()
        if not self._challenge_context_matches(
            challenge, ip_address=ip_address, user_agent=user_agent
        ):
            await self.brute_force_service.record_failure(scope="2fa", identifier=identifier)
            await self._delete_login_challenge(challenge_id)
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_LOGIN_FAILED,
                outcome="failure",
                actor_user_id=None,
                target_user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"reason": "challenge_context_mismatch"},
            )
            await session.commit()
            raise InvalidChallengeException()

        user_id_raw = challenge.get("user_id")
        if not user_id_raw:
            raise InvalidChallengeException()
        try:
            challenge_user_id = UUID(user_id_raw)
        except ValueError as exc:
            raise InvalidChallengeException() from exc

        user = await self.user_repository.get_by_id(session, challenge_user_id)
        if user is None:
            raise InvalidChallengeException()

        if not user.is_active:
            await self._delete_login_challenge(challenge_id)
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_LOGIN_FAILED,
                outcome="failure",
                actor_user_id=user.id,
                target_user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"reason": "inactive_account", "via": "2fa_challenge"},
            )
            await session.commit()
            raise InvalidCredentialsException()

        try:
            await self.two_factor_service.verify_for_login(
                session,
                user=user,
                totp_code=totp_code,
                backup_code=backup_code,
            )
        except InvalidTwoFactorCodeException:
            await self.brute_force_service.record_failure(scope="2fa", identifier=identifier)
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_LOGIN_FAILED,
                outcome="failure",
                actor_user_id=user.id,
                target_user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"reason": "invalid_2fa"},
            )
            await session.commit()
            raise

        await self.brute_force_service.clear_failures(scope="2fa", identifier=identifier)
        await self._delete_login_challenge(challenge_id)

        token_pair = await self.refresh_token_service.issue_for_user(
            session,
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.audit_service.log_event(
            session,
            event_type=AUDIT_LOGIN_SUCCESS,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"via": "2fa_challenge"},
        )
        await session.commit()
        return token_pair

    async def refresh_tokens(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        try:
            token_pair = await self.refresh_token_service.rotate(
                session,
                raw_refresh_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except TokenReuseDetectedException as exc:
            if exc.session_id is not None:
                await self._mark_access_session_revoked(exc.session_id)
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_REFRESH_REUSE_DETECTED,
                outcome="failure",
                actor_user_id=None,
                target_user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"reason": "reused_refresh"},
            )
            await session.commit()
            raise
        except InvalidTokenException:
            await self.audit_service.log_event(
                session,
                event_type=AUDIT_REFRESH_REUSE_DETECTED,
                outcome="failure",
                actor_user_id=None,
                target_user_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                payload={"reason": "invalid_or_reused_refresh"},
            )
            await session.commit()
            raise

        await self.audit_service.log_event(
            session,
            event_type=AUDIT_REFRESH_SUCCESS,
            outcome="success",
            actor_user_id=None,
            target_user_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await session.commit()
        return token_pair

    async def revoke_refresh_token(
        self,
        session: AsyncSession,
        *,
        refresh_token: str,
        revoke_family: bool,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        revocation = await self.refresh_token_service.revoke(
            session,
            raw_refresh_token=refresh_token,
            revoke_family=revoke_family,
            reason="logout",
        )
        if revocation is not None:
            await self._mark_access_session_revoked(revocation.session_id)
        await self.audit_service.log_event(
            session,
            event_type=AUDIT_REFRESH_REVOKED,
            outcome="success",
            actor_user_id=None,
            target_user_id=None,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={"family_id": str(revocation.family_id) if revocation else None},
        )
        await session.commit()

    async def _mark_access_session_revoked(self, session_id: UUID) -> None:
        await self.redis.set(
            access_session_revoked_key(str(session_id)),
            "1",
            ex=max(self.settings.jwt_access_ttl_seconds, 60),
        )

    async def _create_login_challenge(
        self,
        *,
        user_id: UUID,
        ip_address: str | None,
    ) -> str:
        challenge_id = str(uuid4())
        payload = {
            "user_id": str(user_id),
            "ip_fingerprint": self._context_fingerprint(ip_address),
        }
        key = login_challenge_key(challenge_id)
        await self.redis.set(key, json.dumps(payload), ex=self.settings.login_challenge_ttl_seconds)
        return challenge_id

    async def _get_login_challenge(self, challenge_id: str) -> dict[str, str | None] | None:
        key = login_challenge_key(challenge_id)
        raw = await self.redis.get(key)
        if raw is None:
            return None
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return {
            "user_id": decoded.get("user_id"),
            "ip_fingerprint": decoded.get("ip_fingerprint"),
        }

    async def _delete_login_challenge(self, challenge_id: str) -> None:
        key = login_challenge_key(challenge_id)
        await self.redis.delete(key)

    def _context_fingerprint(self, value: str | None) -> str:
        normalized = normalize_optional(value)
        return stable_hmac_digest(value=normalized, pepper=self.settings.privacy_key_pepper_value)

    def _challenge_context_matches(
        self,
        challenge: dict[str, str | None],
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> bool:
        """Bind challenge to client IP only; User-Agent is too unstable on mobile networks."""
        _ = user_agent
        expected_ip = challenge.get("ip_fingerprint")
        if expected_ip is None:
            return False
        actual_ip = self._context_fingerprint(ip_address)
        return hmac.compare_digest(expected_ip, actual_ip)
