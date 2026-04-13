from __future__ import annotations

TOKEN_TYPE_ACCESS = "access"

ROLE_USER = "user"
ROLE_ADMIN = "admin"

PERMISSION_PROFILE_READ_SELF = "profile:read:self"
PERMISSION_PROFILE_WRITE_SELF = "profile:write:self"
PERMISSION_USERS_READ = "users:read"
PERMISSION_USERS_WRITE = "users:write"
PERMISSION_ROLES_ASSIGN = "roles:assign"

AUDIT_PROFILE_UPDATED = "user.profile.updated"
AUDIT_ROLE_ASSIGNED = "user.role.assigned"
AUDIT_USER_BOOTSTRAPPED = "user.bootstrap"
