from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    request_id: str | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
