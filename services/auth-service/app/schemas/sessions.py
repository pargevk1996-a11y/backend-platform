from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SessionInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    email: str
    client_ip: str | None
    two_factor_enabled: bool
