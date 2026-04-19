from __future__ import annotations

from uuid import UUID

from fastapi import Request
from redis.asyncio import Redis

from app.exceptions.auth import UnauthorizedException
from app.integrations.redis.keys import access_session_revoked_key
from shared.http import extract_bearer_token as _shared_extract_bearer_token
from shared.http import get_client_ip as _shared_get_client_ip
from shared.http import is_trusted_proxy as _is_trusted_proxy  # noqa: F401  (re-export)


def get_client_ip(request: Request, trusted_proxy_ips: list[str] | None = None) -> str:
    return _shared_get_client_ip(request, trusted_proxy_ips)


async def ensure_access_session_active(redis: Redis, session_id: UUID) -> None:
    if await redis.exists(access_session_revoked_key(str(session_id))):
        raise UnauthorizedException("Access session revoked")


def extract_bearer_token(request: Request) -> str:
    token = _shared_extract_bearer_token(request)
    if token is None:
        raise UnauthorizedException("Missing or invalid authorization header")
    return token
