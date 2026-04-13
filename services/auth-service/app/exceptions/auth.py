from __future__ import annotations

from app.exceptions.base import AppException


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message=message, error_code="UNAUTHORIZED", status_code=401)


class InvalidCredentialsException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS",
            status_code=401,
        )


class UserAlreadyExistsException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="User already exists",
            error_code="USER_ALREADY_EXISTS",
            status_code=409,
        )


class AccountLockedException(AppException):
    def __init__(self, message: str = "Too many failed attempts. Try later") -> None:
        super().__init__(message=message, error_code="ACCOUNT_LOCKED", status_code=423)


class TooManyRequestsException(AppException):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(message=message, error_code="TOO_MANY_REQUESTS", status_code=429)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(message=message, error_code="BAD_REQUEST", status_code=400)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message=message, error_code="SERVICE_UNAVAILABLE", status_code=503)
