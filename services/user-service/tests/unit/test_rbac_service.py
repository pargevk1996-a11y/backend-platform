from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.core.constants import ROLE_USER
from app.services.rbac_service import RBACService


@dataclass
class FakeRole:
    id: UUID
    name: str
    description: str | None = None


@dataclass
class FakePermission:
    id: UUID
    name: str
    description: str | None = None


class FakeRBACRepository:
    def __init__(self) -> None:
        self.roles: dict[str, FakeRole] = {}
        self.permissions: dict[str, FakePermission] = {}
        self.user_roles: set[tuple[UUID, UUID]] = set()
        self.role_permissions: set[tuple[UUID, UUID]] = set()

    async def get_role_by_name(self, session, role_name: str):
        return self.roles.get(role_name)

    async def get_permission_by_name(self, session, permission_name: str):
        return self.permissions.get(permission_name)

    async def create_role(self, session, *, name: str, description: str | None):
        role = FakeRole(id=uuid4(), name=name, description=description)
        self.roles[name] = role
        return role

    async def create_permission(self, session, *, name: str, description: str | None):
        permission = FakePermission(id=uuid4(), name=name, description=description)
        self.permissions[name] = permission
        return permission

    async def ensure_role_permission(self, session, *, role_id: UUID, permission_id: UUID):
        self.role_permissions.add((role_id, permission_id))

    async def assign_role_to_user(self, session, *, user_id: UUID, role_id: UUID):
        self.user_roles.add((user_id, role_id))

    async def list_roles_for_user(self, session, user_id: UUID):
        role_ids = {role_id for uid, role_id in self.user_roles if uid == user_id}
        return [role for role in self.roles.values() if role.id in role_ids]

    async def list_permission_names_for_user(self, session, user_id: UUID):
        role_ids = {role_id for uid, role_id in self.user_roles if uid == user_id}
        permission_ids = {pid for rid, pid in self.role_permissions if rid in role_ids}
        return sorted([perm.name for perm in self.permissions.values() if perm.id in permission_ids])


@pytest.mark.asyncio
async def test_seed_and_assign_default_role() -> None:
    repository = FakeRBACRepository()
    service = RBACService(repository)

    await service.ensure_seed_data(None)

    assert ROLE_USER in repository.roles

    user_id = uuid4()
    await service.ensure_default_user_role(None, user_id=user_id)

    roles = await service.list_role_names_for_user(None, user_id=user_id)
    assert ROLE_USER in roles

    permissions = await service.list_permission_names_for_user(None, user_id=user_id)
    assert "profile:read:self" in permissions
    assert "profile:write:self" in permissions
