from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TokenClaims:
    sub: str
    jti: str
    token_type: str
    session_id: str | None = None
    family_id: str | None = None
