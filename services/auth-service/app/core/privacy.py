from __future__ import annotations

import hmac
from hashlib import sha256


def stable_hmac_digest(*, value: str, pepper: str) -> str:
    """Return deterministic keyed digest for privacy-preserving identifiers."""
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), sha256).hexdigest()


def normalize_optional(value: str | None) -> str:
    if value is None:
        return "<none>"
    normalized = value.strip()
    return normalized or "<empty>"
