from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppException(Exception):
    message: str
    error_code: str
    status_code: int

    def __str__(self) -> str:
        return self.message
