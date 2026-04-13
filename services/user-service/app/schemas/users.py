from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    external_subject: str
    is_active: bool


class UserMeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    external_subject: str
    roles: list[str]
    permissions: list[str]
