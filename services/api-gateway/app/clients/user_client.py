from __future__ import annotations

import httpx
from httpx._types import QueryParamTypes


class UserClient:
    def __init__(self, *, base_url: str, http_client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client

    async def request(
        self,
        *,
        method: str,
        path: str,
        params: QueryParamTypes,
        headers: dict[str, str],
        content: bytes,
    ) -> httpx.Response:
        return await self.http_client.request(
            method=method,
            url=f"{self.base_url}{path}",
            params=params,
            headers=headers,
            content=content,
        )
