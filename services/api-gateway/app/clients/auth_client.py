from __future__ import annotations

import httpx
from httpx._types import QueryParamTypes

from app.exceptions.gateway import UnauthorizedException, UpstreamServiceException


class AuthClient:
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

    async def touch_session(self, *, access_token: str) -> None:
        try:
            response = await self.http_client.request(
                method="POST",
                url=f"{self.base_url}/v1/sessions/touch",
                headers={"Authorization": f"Bearer {access_token}"},
                content=b"",
            )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceException("Upstream timeout") from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceException("Upstream request failed") from exc

        if response.status_code in {401, 403}:
            raise UnauthorizedException("Session expired due to inactivity")
        if response.status_code >= 400:
            raise UpstreamServiceException("Upstream request failed")
