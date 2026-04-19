from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Request
from jwt import InvalidTokenError
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.constants import PUBLIC_ENDPOINTS, TOKEN_TYPE_ACCESS
from app.exceptions.gateway import ForbiddenException, UnauthorizedException
from app.integrations.redis.keys import access_session_revoked_key
from shared.http import extract_bearer_token as _shared_extract_bearer_token
from shared.http import get_client_ip as _shared_get_client_ip
from shared.http import is_trusted_proxy as _is_trusted_proxy  # noqa: F401  (public re-export)


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


def get_client_ip(request: Request, trusted_proxy_ips: list[str] | None = None) -> str:
    """Resolve the true client IP; delegates to shared helper for the logic."""
    return _shared_get_client_ip(request, trusted_proxy_ips)


def extract_bearer_token(request: Request, *, settings: Settings) -> str:
    """Extract the Authorization bearer token or raise ``UnauthorizedException``."""
    _ = settings  # kept for API compatibility
    token = _shared_extract_bearer_token(request)
    if token is None:
        raise UnauthorizedException("Missing or invalid authorization header")
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
