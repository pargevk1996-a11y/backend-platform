from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings
from app.core.constants import TOKEN_TYPE_ACCESS
from app.exceptions.auth import ForbiddenException, UnauthorizedException


@dataclass(slots=True, frozen=True)
class AccessTokenClaims:
    sub: UUID
    jti: UUID
    sid: UUID
    token_type: str


class AccessTokenService:
    """Validates access tokens issued by auth-service using PyJWT only."""

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
                    "require": ["sub", "jti", "sid", "type", "iss", "aud", "exp"],
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

        return AccessTokenClaims(
            sub=subject,
            jti=jti,
            sid=sid,
            token_type=token_type,
        )


def get_client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def extract_bearer_token(request) -> str:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedException("Missing bearer token")
    return token


def ensure_permission(permissions: set[str], required: str) -> None:
    if required not in permissions:
        raise ForbiddenException("Insufficient permissions")
