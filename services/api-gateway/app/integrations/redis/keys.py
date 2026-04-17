from __future__ import annotations


def rate_limit_key(*, scope: str, ip: str) -> str:
    return f"rate_limit:sliding:{scope}:{ip}"


def access_session_revoked_key(session_id: str) -> str:
    return f"access_session_revoked:{session_id}"
