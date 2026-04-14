from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    PERMISSION_PROFILE_READ_SELF,
    PERMISSION_PROFILE_WRITE_SELF,
    PERMISSION_ROLES_ASSIGN,
    PERMISSION_USERS_READ,
    PERMISSION_USERS_WRITE,
    ROLE_ADMIN,
    ROLE_USER,
)
from app.exceptions.auth import BadRequestException
from app.models.permission import Permission
from app.models.role import Role
from app.repositories.rbac_repository import RBACRepository


class RBACService:
    """RBAC lifecycle service: seed, resolve permissions, assign roles."""

    def __init__(self, repository: RBACRepository) -> None:
        self.repository = repository

    async def ensure_seed_data(self, session: AsyncSession) -> None:
        user_role = await self._get_or_create_role(session, ROLE_USER, "Default user role")
        admin_role = await self._get_or_create_role(session, ROLE_ADMIN, "Administrative role")

        p_profile_read = await self._get_or_create_permission(
            session,
            PERMISSION_PROFILE_READ_SELF,
            "Read own profile",
        )
        p_profile_write = await self._get_or_create_permission(
            session,
            PERMISSION_PROFILE_WRITE_SELF,
            "Update own profile",
        )
        p_users_read = await self._get_or_create_permission(
            session,
            PERMISSION_USERS_READ,
            "Read user entities",
        )
        p_users_write = await self._get_or_create_permission(
            session,
            PERMISSION_USERS_WRITE,
            "Update user entities",
        )
        p_roles_assign = await self._get_or_create_permission(
            session,
            PERMISSION_ROLES_ASSIGN,
            "Assign roles to users",
        )

        await self.repository.ensure_role_permission(
            session,
            role_id=user_role.id,
            permission_id=p_profile_read.id,
        )
        await self.repository.ensure_role_permission(
            session,
            role_id=user_role.id,
            permission_id=p_profile_write.id,
        )

        for permission in (
            p_profile_read,
            p_profile_write,
            p_users_read,
            p_users_write,
            p_roles_assign,
        ):
            await self.repository.ensure_role_permission(
                session,
                role_id=admin_role.id,
                permission_id=permission.id,
            )

    async def ensure_default_user_role(self, session: AsyncSession, *, user_id: UUID) -> None:
        role = await self.repository.get_role_by_name(session, ROLE_USER)
        if role is None:
            raise RuntimeError("RBAC seed is not initialized")
        await self.repository.assign_role_to_user(session, user_id=user_id, role_id=role.id)

    async def assign_role_by_name(
        self, session: AsyncSession, *, user_id: UUID, role_name: str
    ) -> None:
        role = await self.repository.get_role_by_name(session, role_name)
        if role is None:
            raise BadRequestException("Unknown role")
        await self.repository.assign_role_to_user(session, user_id=user_id, role_id=role.id)

    async def list_role_names_for_user(self, session: AsyncSession, *, user_id: UUID) -> list[str]:
        roles = await self.repository.list_roles_for_user(session, user_id)
        return [role.name for role in roles]

    async def list_permission_names_for_user(
        self, session: AsyncSession, *, user_id: UUID
    ) -> list[str]:
        return await self.repository.list_permission_names_for_user(session, user_id)

    async def permissions_set_for_user(self, session: AsyncSession, *, user_id: UUID) -> set[str]:
        return set(await self.list_permission_names_for_user(session, user_id=user_id))

    async def _get_or_create_role(
        self,
        session: AsyncSession,
        role_name: str,
        description: str,
    ) -> Role:
        role = await self.repository.get_role_by_name(session, role_name)
        if role is not None:
            return role
        return await self.repository.create_role(
            session,
            name=role_name,
            description=description,
        )

    async def _get_or_create_permission(
        self,
        session: AsyncSession,
        permission_name: str,
        description: str,
    ) -> Permission:
        permission = await self.repository.get_permission_by_name(session, permission_name)
        if permission is not None:
            return permission
        return await self.repository.create_permission(
            session,
            name=permission_name,
            description=description,
        )
