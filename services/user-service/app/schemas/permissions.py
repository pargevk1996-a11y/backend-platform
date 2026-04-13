from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PermissionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permissions: list[str]
