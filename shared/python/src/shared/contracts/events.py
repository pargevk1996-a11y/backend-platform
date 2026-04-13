from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AuditEventContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str
    outcome: str
    actor_user_id: str | None = None
    target_user_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    payload: dict[str, str | int | bool | None] = {}
