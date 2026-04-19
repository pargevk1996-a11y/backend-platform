from __future__ import annotations

import hmac
import re
from hashlib import sha256

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value))


def stable_hmac_digest(*, value: str, pepper: str) -> str:
    """Return a deterministic keyed digest for privacy-preserving identifiers.

    Used for hashing IP addresses, emails, and other quasi-identifiers before
    they land in rate-limit keys or audit payloads. The pepper MUST be a
    service-wide secret of at least 32 bytes.
    """
    return hmac.new(pepper.encode("utf-8"), value.encode("utf-8"), sha256).hexdigest()


def normalize_optional(value: str | None) -> str:
    """Normalise an optional user-supplied string for stable fingerprinting."""
    if value is None:
        return "<none>"
    normalized = value.strip()
    return normalized or "<empty>"
