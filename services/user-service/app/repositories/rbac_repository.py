from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user_role import UserRole


class RBACRepository:
    async def get_role_by_name(self, session: AsyncSession, role_name: str) -> Role | None:
        stmt = select(Role).where(Role.name == role_name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_permission_by_name(
        self,
        session: AsyncSession,
        permission_name: str,
    ) -> Permission | None:
        stmt = select(Permission).where(Permission.name == permission_name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_role(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str | None,
    ) -> Role:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
        return role

    async def create_permission(
        self,
        session: AsyncSession,
        *,
        name: str,
        description: str | None,
    ) -> Permission:
        permission = Permission(name=name, description=description)
        session.add(permission)
        await session.flush()
        return permission

    async def ensure_role_permission(
        self,
        session: AsyncSession,
        *,
        role_id: UUID,
        permission_id: UUID,
    ) -> None:
        stmt = select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
        await session.flush()

    async def assign_role_to_user(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        role_id: UUID,
    ) -> None:
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return
        session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()

    async def list_roles_for_user(self, session: AsyncSession, user_id: UUID) -> list[Role]:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.name.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_permission_names_for_user(
        self, session: AsyncSession, user_id: UUID
    ) -> list[str]:
        stmt = (
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .distinct()
            .order_by(Permission.name.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def clear_user_roles(self, session: AsyncSession, user_id: UUID) -> None:
        await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
