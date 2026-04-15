from __future__ import annotations


def rate_limit_key(*, scope: str, ip: str, bucket: int) -> str:
    return f"rate_limit:{scope}:{ip}:{bucket}"


def access_session_revoked_key(session_id: str) -> str:
    return f"access_session_revoked:{session_id}"


def brute_force_fail_key(*, scope: str, identifier: str) -> str:
    return f"brute_force:{scope}:{identifier}:fail"


def brute_force_lock_key(*, scope: str, identifier: str) -> str:
    return f"brute_force:{scope}:{identifier}:lock"


def login_challenge_key(challenge_id: str) -> str:
    return f"login_challenge:{challenge_id}"
