from __future__ import annotations

import pytest
from app.api.v1.health import liveness, readiness
from app.core.middleware import SecurityHeadersMiddleware
from fastapi import Request
from starlette.responses import Response


def _request(path: str = "/v1/health/live") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


async def _asgi_app(scope: object, receive: object, send: object) -> None:
    return None


async def _call_next(request: Request) -> Response:
    return Response()


@pytest.mark.asyncio
async def test_liveness_returns_ok() -> None:
    response = await liveness()

    assert response.status == "ok"


@pytest.mark.asyncio
async def test_readiness_returns_ok() -> None:
    response = await readiness()

    assert response.status == "ok"


@pytest.mark.asyncio
async def test_security_headers_are_applied() -> None:
    middleware = SecurityHeadersMiddleware(_asgi_app)

    response = await middleware.dispatch(_request(), _call_next)

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
