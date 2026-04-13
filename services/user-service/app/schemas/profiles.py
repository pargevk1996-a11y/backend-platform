from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    display_name: str | None
    locale: str
    timezone: str
    avatar_url: str | None


class UpdateProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: str = Field(default="en-US", min_length=2, max_length=16)
    timezone: str = Field(default="UTC", min_length=2, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)
