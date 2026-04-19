"""Backwards-compatible shim: the canonical implementation lives in `shared`."""
from __future__ import annotations

from shared.security import normalize_optional, stable_hmac_digest

__all__ = ["normalize_optional", "stable_hmac_digest"]
