from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings
from app.exceptions.auth import BadRequestException

MIN_PASSWORD_LENGTH = 12
# Capped to avoid Argon2 DoS via absurdly long input.
MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_CLASSES = 3

_CHAR_CLASSES: tuple[re.Pattern[str], ...] = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"\d"),
    re.compile(r"[^0-9A-Za-z]"),
)


class PasswordService:
    """Argon2-based password and backup-code hashing service."""

    def __init__(self, settings: Settings) -> None:
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_length,
            salt_len=settings.argon2_salt_length,
        )
        # Pre-hashed sentinel used to reduce user-enumeration timing differences.
        self._dummy_password_hash = self._hasher.hash("TimingMitigationPassword!123")

    def validate_password_policy(self, password: str) -> None:
        if not isinstance(password, str):
            raise BadRequestException("Password must be a string")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise BadRequestException(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
            )
        if len(password) > MAX_PASSWORD_LENGTH:
            raise BadRequestException(
                f"Password must be at most {MAX_PASSWORD_LENGTH} characters long"
            )
        classes_present = sum(bool(pattern.search(password)) for pattern in _CHAR_CLASSES)
        if classes_present < MIN_PASSWORD_CLASSES:
            raise BadRequestException(
                "Password must contain at least "
                f"{MIN_PASSWORD_CLASSES} of: lowercase, uppercase, digit, symbol"
            )

    def hash_password(self, password: str) -> str:
        self.validate_password_policy(password)
        return self._hasher.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bool(self._hasher.verify(password_hash, password))
        except VerifyMismatchError:
            return False

    def verify_against_dummy_hash(self, password: str) -> None:
        # The result is intentionally ignored. This call exists only to consume similar CPU time.
        try:
            self._hasher.verify(self._dummy_password_hash, password)
        except VerifyMismatchError:
            return

    def hash_backup_code(self, code: str) -> str:
        return self._hasher.hash(code)

    def verify_backup_code(self, code: str, code_hash: str) -> bool:
        try:
            return bool(self._hasher.verify(code_hash, code))
        except VerifyMismatchError:
            return False
