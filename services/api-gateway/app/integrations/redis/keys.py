from __future__ import annotations


def rate_limit_key(*, scope: str, ip: str, bucket: int) -> str:
    return f"rate_limit:{scope}:{ip}:{bucket}"


def access_session_revoked_key(session_id: str) -> str:
    return f"access_session_revoked:{session_id}"
