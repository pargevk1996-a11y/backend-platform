from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class Argon2Hasher:
    def __init__(
        self,
        *,
        time_cost: int = 3,
        memory_cost: int = 65536,
        parallelism: int = 4,
        hash_len: int = 32,
        salt_len: int = 16,
    ) -> None:
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
        )

    def hash(self, value: str) -> str:
        return self._hasher.hash(value)

    def verify(self, value: str, value_hash: str) -> bool:
        try:
            return bool(self._hasher.verify(value_hash, value))
        except VerifyMismatchError:
            return False
