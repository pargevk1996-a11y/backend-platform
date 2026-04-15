from __future__ import annotations

from ipaddress import ip_address, ip_network
from uuid import UUID

from fastapi import Request
from redis.asyncio import Redis

from app.exceptions.auth import UnauthorizedException
from app.integrations.redis.keys import access_session_revoked_key


def _is_trusted_proxy(client_host: str | None, trusted_proxy_ips: list[str] | None) -> bool:
    if not client_host:
        return False
    for trusted in trusted_proxy_ips or []:
        candidate = trusted.strip()
        if not candidate:
            continue
        if candidate == client_host:
            return True
        try:
            client_ip = ip_address(client_host)
            if "/" in candidate:
                if client_ip in ip_network(candidate, strict=False):
                    return True
            elif client_ip == ip_address(candidate):
                return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request, trusted_proxy_ips: list[str] | None = None) -> str:
    client_host = request.client.host if request.client and request.client.host else None
    xff = request.headers.get("x-forwarded-for")
    if xff and _is_trusted_proxy(client_host, trusted_proxy_ips):
        first = xff.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if client_host:
        return client_host
    return "unknown"


async def ensure_access_session_active(redis: Redis, session_id: UUID) -> None:
    if await redis.exists(access_session_revoked_key(str(session_id))):
        raise UnauthorizedException("Access session revoked")


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedException("Missing bearer token")
    return token
