"""Backwards-compatible shim: the canonical implementation lives in `shared`."""
from __future__ import annotations

from shared.security import stable_hmac_digest

__all__ = ["stable_hmac_digest"]
