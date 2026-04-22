from __future__ import annotations

import re

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.token import TokenPairResponse


class RegisterResponse(BaseModel):
    """Registration creates the account only; clients must call ``POST /auth/login`` for tokens."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["created"] = "created"


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=256)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must include at least one letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must include at least one digit")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class LoginTwoFactorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    challenge_id: str
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    backup_code: str | None = Field(default=None, min_length=5, max_length=32)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_2fa: bool
    challenge_id: str | None = None
    tokens: TokenPairResponse | None = None


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must include at least one letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must include at least one digit")
        return value


class PasswordResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    """False when outbound email was skipped (e.g. SMTP not configured with AUTH_ALLOW_MISSING_SMTP)."""
    email_sent: bool = True
