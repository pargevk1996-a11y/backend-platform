from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SharedAppException(Exception):
    message: str
    error_code: str

    def __str__(self) -> str:
        return self.message
