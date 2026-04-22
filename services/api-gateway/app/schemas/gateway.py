from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProxyMetaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proxied_to: str
    upstream_status: int
