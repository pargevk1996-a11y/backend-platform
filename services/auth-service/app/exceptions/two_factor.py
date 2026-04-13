from __future__ import annotations

from app.exceptions.base import AppException


class TwoFactorRequiredException(AppException):
    def __init__(self, challenge_id: str) -> None:
        super().__init__(
            message="Two-factor authentication required",
            error_code="TWO_FACTOR_REQUIRED",
            status_code=202,
        )
        self.challenge_id = challenge_id


class InvalidTwoFactorCodeException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid two-factor code",
            error_code="INVALID_2FA_CODE",
            status_code=401,
        )


class TwoFactorNotEnabledException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Two-factor authentication is not enabled",
            error_code="2FA_NOT_ENABLED",
            status_code=400,
        )


class TwoFactorAlreadyEnabledException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Two-factor authentication is already enabled",
            error_code="2FA_ALREADY_ENABLED",
            status_code=409,
        )


class InvalidChallengeException(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Invalid or expired challenge",
            error_code="INVALID_CHALLENGE",
            status_code=401,
        )
