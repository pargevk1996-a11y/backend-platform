from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import AUDIT_PROFILE_UPDATED, AUDIT_USER_BOOTSTRAPPED
from app.exceptions.auth import NotFoundException
from app.models.app_user import AppUser
from app.models.user_profile import UserProfile
from app.repositories.profile_repository import ProfileRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.rbac_service import RBACService


@dataclass(slots=True)
class UserContext:
    user: AppUser
    profile: UserProfile
    roles: list[str]
    permissions: set[str]


class UserService:
    """User-domain service responsible for profile and identity projection."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        profile_repository: ProfileRepository,
        rbac_service: RBACService,
        audit_service: AuditService,
    ) -> None:
        self.user_repository = user_repository
        self.profile_repository = profile_repository
        self.rbac_service = rbac_service
        self.audit_service = audit_service

    async def bootstrap_from_subject(
        self,
        session: AsyncSession,
        *,
        subject: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> AppUser:
        existing = await self.user_repository.get_by_subject(session, str(subject))
        if existing is not None:
            return existing

        user = await self.user_repository.create(
            session,
            user_id=subject,
            external_subject=str(subject),
        )
        await self.rbac_service.ensure_default_user_role(session, user_id=user.id)
        await self.audit_service.log_event(
            session,
            event_type=AUDIT_USER_BOOTSTRAPPED,
            outcome="success",
            actor_user_id=user.id,
            target_user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return user

    async def context_for_subject(
        self,
        session: AsyncSession,
        *,
        subject: UUID,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserContext:
        user = await self.bootstrap_from_subject(
            session,
            subject=subject,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        profile = await self.profile_repository.get_by_user_id(session, user.id)
        if profile is None:
            raise NotFoundException("User profile not found")

        roles = await self.rbac_service.list_role_names_for_user(session, user_id=user.id)
        permissions = set(
            await self.rbac_service.list_permission_names_for_user(session, user_id=user.id)
        )

        return UserContext(user=user, profile=profile, roles=roles, permissions=permissions)

    async def get_user_by_id(self, session: AsyncSession, user_id: UUID) -> AppUser:
        user = await self.user_repository.get_by_id(session, user_id)
        if user is None:
            raise NotFoundException("User not found")
        return user

    async def update_own_profile(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        actor_user_id: UUID,
        display_name: str | None,
        locale: str,
        timezone: str,
        avatar_url: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> UserProfile:
        profile = await self.profile_repository.get_by_user_id(session, user_id)
        if profile is None:
            raise NotFoundException("User profile not found")

        updated = await self.profile_repository.update(
            session,
            profile=profile,
            display_name=display_name,
            locale=locale,
            timezone=timezone,
            avatar_url=avatar_url,
        )
        await self.audit_service.log_event(
            session,
            event_type=AUDIT_PROFILE_UPDATED,
            outcome="success",
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload={
                "locale": locale,
                "timezone": timezone,
                "has_avatar": bool(avatar_url),
            },
        )
        return updated
