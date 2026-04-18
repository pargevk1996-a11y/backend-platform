from __future__ import annotations

import httpx
import pytest
from app.clients.auth_client import AuthClient
from app.exceptions.gateway import UnauthorizedException, UpstreamServiceException


@pytest.mark.asyncio
async def test_touch_session_succeeds_on_200() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/sessions/touch"
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(200, json={"message": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        auth_client = AuthClient(base_url="http://auth-service:8001", http_client=client)
        await auth_client.touch_session(access_token="access-token")


@pytest.mark.asyncio
async def test_touch_session_rejects_idle_session() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(401, json={"message": "Session expired due to inactivity"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        auth_client = AuthClient(base_url="http://auth-service:8001", http_client=client)
        with pytest.raises(UnauthorizedException, match="Session expired due to inactivity"):
            await auth_client.touch_session(access_token="access-token")


@pytest.mark.asyncio
async def test_touch_session_raises_on_upstream_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(502, json={"message": "bad gateway"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        auth_client = AuthClient(base_url="http://auth-service:8001", http_client=client)
        with pytest.raises(UpstreamServiceException, match="Upstream request failed"):
            await auth_client.touch_session(access_token="access-token")
