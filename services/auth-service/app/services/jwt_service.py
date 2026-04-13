from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from app.core.config import Settings
from app.core.constants import TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH
from app.core.jwt import TokenClaims
from app.exceptions.token import InvalidTokenException


class JWTService:
    """JWT issuing and verification service based on PyJWT."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _signing_key(self) -> str:
        return self.settings.jwt_private_key_value

    def _verification_key(self) -> str:
        if self.settings.jwt_algorithm.startswith("HS"):
            return self.settings.jwt_private_key_value
        return self.settings.jwt_public_key_value

    @staticmethod
    def generate_jti() -> UUID:
        return uuid4()

    def issue_access_token(self, *, subject: UUID, session_id: UUID) -> tuple[str, int]:
        now = datetime.now(tz=timezone.utc)
        exp = now + timedelta(seconds=self.settings.jwt_access_ttl_seconds)
        payload: dict[str, str | int | datetime] = {
            "sub": str(subject),
            "jti": str(self.generate_jti()),
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": exp,
            "type": TOKEN_TYPE_ACCESS,
            "sid": str(session_id),
        }
        token = jwt.encode(payload, key=self._signing_key(), algorithm=self.settings.jwt_algorithm)
        return token, self.settings.jwt_access_ttl_seconds

    def issue_refresh_token(
        self,
        *,
        subject: UUID,
        session_id: UUID,
        family_id: UUID,
        jti: UUID,
    ) -> tuple[str, datetime]:
        now = datetime.now(tz=timezone.utc)
        exp = now + timedelta(seconds=self.settings.jwt_refresh_ttl_seconds)
        payload: dict[str, str | int | datetime] = {
            "sub": str(subject),
            "jti": str(jti),
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": exp,
            "type": TOKEN_TYPE_REFRESH,
            "sid": str(session_id),
            "family_id": str(family_id),
        }
        token = jwt.encode(payload, key=self._signing_key(), algorithm=self.settings.jwt_algorithm)
        return token, exp

    def decode_and_validate(self, token: str, *, expected_type: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                key=self._verification_key(),
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={
                    "require": ["sub", "jti", "iss", "aud", "iat", "nbf", "exp", "type"],
                },
            )
        except InvalidTokenError as exc:
            raise InvalidTokenException() from exc

        token_type = payload.get("type")
        if token_type != expected_type:
            raise InvalidTokenException("Unexpected token type")

        sub = payload.get("sub")
        jti = payload.get("jti")
        if not isinstance(sub, str) or not isinstance(jti, str):
            raise InvalidTokenException("Malformed token claims")

        session_id = payload.get("sid")
        family_id = payload.get("family_id")
        if session_id is not None and not isinstance(session_id, str):
            raise InvalidTokenException("Malformed sid claim")
        if family_id is not None and not isinstance(family_id, str):
            raise InvalidTokenException("Malformed family_id claim")

        return TokenClaims(
            sub=sub,
            jti=jti,
            token_type=token_type,
            session_id=session_id,
            family_id=family_id,
        )
