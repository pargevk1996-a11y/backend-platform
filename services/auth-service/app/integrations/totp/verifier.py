from __future__ import annotations

import time

import pyotp
from pyotp.utils import strings_equal


def verify_totp_code(
    *,
    secret: str,
    code: str,
    interval_seconds: int,
    valid_window: int = 1,
) -> tuple[bool, int]:
    totp = pyotp.TOTP(secret, interval=interval_seconds)
    current_timecode = int(time.time()) // interval_seconds
    for offset in range(-valid_window, valid_window + 1):
        candidate_timecode = current_timecode + offset
        if candidate_timecode < 0:
            continue
        candidate_code = totp.at(candidate_timecode * interval_seconds)
        if strings_equal(str(code), str(candidate_code)):
            return True, candidate_timecode
    return False, current_timecode
