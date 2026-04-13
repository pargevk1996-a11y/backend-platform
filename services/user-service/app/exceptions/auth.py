from __future__ import annotations

from app.exceptions.base import AppException


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message=message, error_code="UNAUTHORIZED", status_code=401)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message=message, error_code="FORBIDDEN", status_code=403)


class TooManyRequestsException(AppException):
    def __init__(self, message: str = "Too many requests") -> None:
        super().__init__(message=message, error_code="TOO_MANY_REQUESTS", status_code=429)


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request") -> None:
        super().__init__(message=message, error_code="BAD_REQUEST", status_code=400)


class NotFoundException(AppException):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message=message, error_code="NOT_FOUND", status_code=404)
