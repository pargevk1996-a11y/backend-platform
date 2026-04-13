from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserProfileContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    display_name: str | None
    locale: str
    timezone: str
    avatar_url: str | None
