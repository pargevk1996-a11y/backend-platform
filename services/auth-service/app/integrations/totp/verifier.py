from __future__ import annotations

import time

import pyotp


def verify_totp_code(
    *,
    secret: str,
    code: str,
    interval_seconds: int,
    valid_window: int = 1,
) -> tuple[bool, int]:
    totp = pyotp.TOTP(secret, interval=interval_seconds)
    now = int(time.time())
    is_valid = bool(totp.verify(code, valid_window=valid_window, for_time=now))
    timecode = now // interval_seconds
    return is_valid, timecode
