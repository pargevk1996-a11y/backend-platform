from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def sanitize_validation_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for error in errors:
        cleaned = dict(error)
        cleaned.pop("input", None)
        sanitized.append(cleaned)
    return sanitized
