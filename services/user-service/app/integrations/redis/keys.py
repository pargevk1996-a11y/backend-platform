from __future__ import annotations


def rate_limit_key(*, scope: str, ip: str, bucket: int) -> str:
    return f"rate_limit:{scope}:{ip}:{bucket}"
