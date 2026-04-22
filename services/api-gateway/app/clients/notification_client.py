from __future__ import annotations

import httpx
from httpx._types import QueryParamTypes


class NotificationClient:
    def __init__(self, *, base_url: str | None, http_client: httpx.AsyncClient) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.http_client = http_client

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def request(
        self,
        *,
        method: str,
        path: str,
        params: QueryParamTypes,
        headers: dict[str, str],
        content: bytes,
    ) -> httpx.Response:
        if not self.is_configured:
            raise RuntimeError("Notification service is not configured")
        return await self.http_client.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            headers=headers,
            content=content,
        )
