from __future__ import annotations

from fastapi import Header


def idempotency_key_header(idempotency_key: str | None = Header(default=None)) -> str | None:
    return idempotency_key
