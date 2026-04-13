from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.clients.auth_client import AuthClient
from app.clients.notification_client import NotificationClient
from app.clients.user_client import UserClient
from app.exceptions.gateway import RouteNotFoundException, UpstreamServiceException


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


@dataclass(slots=True)
class ProxiedResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]


class RoutingService:
    """Routes incoming gateway requests to whitelisted upstream services."""

    def __init__(
        self,
        *,
        auth_client: AuthClient,
        user_client: UserClient,
        notification_client: NotificationClient,
    ) -> None:
        self.auth_client = auth_client
        self.user_client = user_client
        self.notification_client = notification_client

    def resolve_service(self, path: str):
        if path.startswith("/v1/auth") or path.startswith("/v1/tokens"):
            return self.auth_client
        if path.startswith("/v1/two-factor") or path.startswith("/v1/sessions"):
            return self.auth_client
        if path.startswith("/v1/users") or path.startswith("/v1/profiles"):
            return self.user_client
        if path.startswith("/v1/roles") or path.startswith("/v1/permissions"):
            return self.user_client
        if path.startswith("/v1/notify"):
            return self.notification_client
        raise RouteNotFoundException()

    async def forward(
        self,
        *,
        method: str,
        path: str,
        params: list[tuple[str, str]] | None,
        headers: dict[str, str],
        body: bytes,
    ) -> ProxiedResponse:
        target_client = self.resolve_service(path)
        safe_headers = self._sanitize_request_headers(headers)

        try:
            response = await target_client.request(
                method=method,
                path=path,
                params=params,
                headers=safe_headers,
                content=body,
            )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceException("Upstream timeout") from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceException("Upstream request failed") from exc

        return ProxiedResponse(
            status_code=response.status_code,
            body=response.content,
            headers=self._sanitize_response_headers(response.headers),
        )

    def _sanitize_request_headers(self, headers: dict[str, str]) -> dict[str, str]:
        safe: dict[str, str] = {}
        for key, value in headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP_HEADERS or lower == "host" or lower == "content-length":
                continue
            safe[key] = value
        return safe

    def _sanitize_response_headers(self, headers: httpx.Headers) -> dict[str, str]:
        safe: dict[str, str] = {}
        for key, value in headers.items():
            lower = key.lower()
            if lower in HOP_BY_HOP_HEADERS or lower == "content-length":
                continue
            safe[key] = value
        return safe
