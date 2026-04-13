from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RolesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: list[str]


class AssignRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role_name: str = Field(min_length=2, max_length=64)
