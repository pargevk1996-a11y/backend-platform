# User Service API

Base path: `/v1`

## Security model
- All business endpoints require access token from `auth-service`.
- Token validation checks `iss`, `aud`, `exp`, `type`, `jti`, `sid`.
- RBAC checks are enforced for role and permission management endpoints.

## Endpoints

### `GET /users/me`
- Returns current user profile derived from access token subject.

### `GET /users/{user_id}`
- Returns user public/admin data.
- Protected by permission checks.

### `PATCH /users/{user_id}`
- Updates user state flags and operational attributes.
- Intended for privileged clients.

### `GET /profiles/me`
- Returns extended profile of current user.

### `PATCH /profiles/me`
- Updates own profile fields.
- Rate limited.

### `GET /roles`
- Lists system roles and attached permissions.

### `POST /roles`
- Creates role.
- Protected by RBAC and rate limiting.

### `POST /roles/{role_id}/permissions/{permission_id}`
- Assigns permission to role.

### `GET /permissions`
- Lists all permissions.

### `POST /users/{user_id}/roles/{role_id}`
- Assigns role to user.

### `DELETE /users/{user_id}/roles/{role_id}`
- Removes role from user.

### `GET /health/live`
- Liveness check.

### `GET /health/ready`
- Readiness check (DB + Redis).
