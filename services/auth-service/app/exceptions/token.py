from __future__ import annotations

from app.exceptions.base import AppException


class InvalidTokenException(AppException):
    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message=message, error_code="INVALID_TOKEN", status_code=401)


class RevokedTokenException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Token revoked",
            error_code="TOKEN_REVOKED",
            status_code=401,
        )


class TokenReuseDetectedException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Refresh token reuse detected",
            error_code="TOKEN_REUSE_DETECTED",
            status_code=401,
        )
