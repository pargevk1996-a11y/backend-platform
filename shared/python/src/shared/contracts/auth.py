from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TokenPairContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
