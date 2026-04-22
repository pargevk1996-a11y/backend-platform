from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TwoFactorSetupResponse(BaseModel):
    """Setup returns QR and one-time backup codes (TOTP secret is not exposed as text)."""

    model_config = ConfigDict(extra="forbid")

    qr_png_base64: str
    backup_codes: list[str] = Field(min_length=10, max_length=10)


class TwoFactorEnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    totp_code: str = Field(min_length=6, max_length=8)


class TwoFactorDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    password: str = Field(min_length=1, max_length=256)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    backup_code: str | None = Field(default=None, min_length=5, max_length=32)


class BackupCodesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backup_codes: list[str]


class RegenerateBackupCodesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    totp_code: str | None = Field(default=None, min_length=6, max_length=8)
    backup_code: str | None = Field(default=None, min_length=5, max_length=32)
