from __future__ import annotations

import httpx


class NotificationClient:
    def __init__(self, *, base_url: str | None, http_client: httpx.AsyncClient) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.http_client = http_client

    async def request(
        self,
        *,
        method: str,
        path: str,
        params: list[tuple[str, str]] | None,
        headers: dict[str, str],
        content: bytes,
    ) -> httpx.Response:
        if not self.base_url:
            raise RuntimeError("Notification service is not configured")
        return await self.http_client.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            headers=headers,
            content=content,
        )
