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

FORWARDED_HEADERS = {
    "forwarded",
    "x-forwarded-for",
    "x-real-ip",
}

BLOCKED_RESPONSE_HEADERS = {
    "server",
    "set-cookie",
    "x-powered-by",
}

ALLOWED_REQUEST_HEADERS = {
    "authorization": "Authorization",
    "content-type": "Content-Type",
    "accept": "Accept",
    "x-request-id": "X-Request-ID",
    "x-csrf-token": "X-CSRF-Token",
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

    @staticmethod
    def _matches_prefix(path: str, prefix: str) -> bool:
        normalized_path = path.rstrip("/") or "/"
        normalized_prefix = prefix.rstrip("/") or "/"
        return normalized_path == normalized_prefix or normalized_path.startswith(
            f"{normalized_prefix}/"
        )

    def resolve_service(self, path: str) -> AuthClient | UserClient | NotificationClient:
        if any(
            self._matches_prefix(path, prefix)
            for prefix in ("/v1/auth", "/v1/tokens", "/v1/two-factor", "/v1/sessions")
        ):
            return self.auth_client
        if any(
            self._matches_prefix(path, prefix)
            for prefix in ("/v1/users", "/v1/profiles", "/v1/roles", "/v1/permissions")
        ):
            return self.user_client
        if self._matches_prefix(path, "/v1/notify") and self.notification_client.is_configured:
            return self.notification_client
        raise RouteNotFoundException()

    async def forward(
        self,
        *,
        method: str,
        path: str,
        params: httpx.QueryParams,
        headers: dict[str, str],
        body: bytes,
        client_ip: str | None = None,
    ) -> ProxiedResponse:
        target_client = self.resolve_service(path)
        safe_headers = self._sanitize_request_headers(headers)
        if client_ip:
            safe_headers["X-Forwarded-For"] = client_ip

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
            if (
                lower in HOP_BY_HOP_HEADERS
                or lower in FORWARDED_HEADERS
                or lower == "host"
                or lower == "content-length"
            ):
                continue
            canonical = ALLOWED_REQUEST_HEADERS.get(lower)
            if canonical is None:
                continue
            safe[canonical] = value
        return safe

    def _sanitize_response_headers(self, headers: httpx.Headers) -> dict[str, str]:
        safe: dict[str, str] = {}
        for key, value in headers.items():
            lower = key.lower()
            if (
                lower in HOP_BY_HOP_HEADERS
                or lower in BLOCKED_RESPONSE_HEADERS
                or lower == "content-length"
            ):
                continue
            safe[key] = value
        return safe
