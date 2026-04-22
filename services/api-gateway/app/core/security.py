from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from uuid import UUID

import jwt
from fastapi import Request
from jwt import InvalidTokenError
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.constants import PUBLIC_ENDPOINTS, TOKEN_TYPE_ACCESS
from app.exceptions.gateway import ForbiddenException, UnauthorizedException
from app.integrations.redis.keys import access_session_revoked_key


@dataclass(slots=True, frozen=True)
class AccessTokenClaims:
    sub: UUID
    jti: UUID
    sid: UUID
    token_type: str


class AccessTokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decode_access_token(self, raw_token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                raw_token,
                key=self.settings.jwt_public_key_value,
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={
                    "require": [
                        "sub",
                        "jti",
                        "sid",
                        "type",
                        "iss",
                        "aud",
                        "iat",
                        "nbf",
                        "exp",
                    ],
                },
            )
        except InvalidTokenError as exc:
            raise UnauthorizedException("Invalid access token") from exc

        token_type = payload.get("type")
        if token_type != TOKEN_TYPE_ACCESS:
            raise UnauthorizedException("Unexpected token type")

        try:
            subject = UUID(str(payload.get("sub")))
            jti = UUID(str(payload.get("jti")))
            sid = UUID(str(payload.get("sid")))
        except ValueError as exc:
            raise UnauthorizedException("Malformed token claims") from exc

        return AccessTokenClaims(sub=subject, jti=jti, sid=sid, token_type=token_type)


async def ensure_access_session_active(redis: Redis, session_id: UUID) -> None:
    if await redis.exists(access_session_revoked_key(str(session_id))):
        raise UnauthorizedException("Access session revoked")


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


def effective_refresh_cookie_secure(request: Request, settings: Settings) -> bool:
    """Set-Cookie ``Secure`` for the browser BFF refresh cookie.

    - If ``REFRESH_COOKIE_SECURE`` is set in env, that value wins (force on/off).
    - Otherwise: ``Secure`` only when the browser-facing connection is HTTPS
      (direct ``request.url.scheme`` or, behind a **trusted** proxy,
      ``X-Forwarded-Proto: https``). Plain HTTP gets no ``Secure`` so the cookie
      is stored; TLS frontends still get ``Secure``.
    """
    if settings.refresh_cookie_secure is not None:
        return settings.refresh_cookie_secure
    if (request.url.scheme or "").lower() == "https":
        return True
    client_host = request.client.host if request.client and request.client.host else None
    if not _is_trusted_proxy(client_host, settings.trusted_proxy_ips):
        return False
    proto_raw = (request.headers.get("x-forwarded-proto") or "").strip()
    if not proto_raw:
        return False
    first = proto_raw.split(",", maxsplit=1)[0].strip().lower()
    return first == "https"


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


def extract_bearer_token(request: Request, *, settings: Settings) -> str:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedException("Missing bearer token")
    return token


def is_public_endpoint(method: str, path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return (method.upper(), normalized) in PUBLIC_ENDPOINTS


def ensure_authenticated_endpoint(method: str, path: str) -> None:
    if is_public_endpoint(method, path):
        return
    if path.startswith("/v1/health"):
        return
    if path.startswith("/v1/auth") and method.upper() == "POST":
        # Only explicitly whitelisted auth endpoints are public.
        if not is_public_endpoint(method, path):
            raise ForbiddenException("Endpoint requires stronger policy")
