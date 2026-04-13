from __future__ import annotations

import hmac
from hashlib import sha256


def stable_hmac_digest(*, value: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), sha256).hexdigest()
