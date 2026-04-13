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


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message=message, error_code="SERVICE_UNAVAILABLE", status_code=503)


class UpstreamServiceException(AppException):
    def __init__(self, message: str = "Upstream service error") -> None:
        super().__init__(message=message, error_code="UPSTREAM_ERROR", status_code=502)


class RouteNotFoundException(AppException):
    def __init__(self, message: str = "Route not found") -> None:
        super().__init__(message=message, error_code="ROUTE_NOT_FOUND", status_code=404)
