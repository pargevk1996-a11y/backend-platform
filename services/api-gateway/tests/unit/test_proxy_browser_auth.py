from __future__ import annotations

import json

import pytest
from app.api.v1.proxy import proxy_request
from app.core.config import get_settings
from app.core.security import AccessTokenService
from app.services.routing_service import ProxiedResponse
from starlette.requests import Request


class FakeRateLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.redis = object()

    async def check(self, *, request: Request, scope: str, limit_per_minute: int) -> None:
        _ = request
        self.calls.append((scope, limit_per_minute))


class FakeRoutingService:
    def __init__(self, response: ProxiedResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def forward(
        self,
        *,
        method: str,
        path: str,
        params,
        headers: dict[str, str],
        body: bytes,
        client_ip: str | None = None,
    ) -> ProxiedResponse:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "headers": headers,
                "body": body,
                "client_ip": client_ip,
            }
        )
        return self.response


def _request(
    *,
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": encoded_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope, receive)


def _set_cookie_headers(response) -> list[str]:
    return [
        value.decode("latin-1")
        for key, value in response.raw_headers
        if key.decode("latin-1").lower() == "set-cookie"
    ]


@pytest.mark.asyncio
async def test_login_tokens_are_converted_to_browser_cookies() -> None:
    settings = get_settings()
    rate_limiter = FakeRateLimiter()
    routing_service = FakeRoutingService(
        ProxiedResponse(
            status_code=200,
            body=json.dumps(
                {
                    "requires_2fa": False,
                    "tokens": {
                        "access_token": "access-token",
                        "refresh_token": "refresh-token",
                        "expires_in": 900,
                    },
                }
            ).encode("utf-8"),
            headers={"content-type": "application/json"},
        )
    )
    request = _request(
        method="POST",
        path="/v1/auth/login",
        body=json.dumps({"email": "user@example.com", "password": "CorrectPassword!1"}).encode(
            "utf-8"
        ),
        headers={"content-type": "application/json"},
    )

    response = await proxy_request(
        full_path="auth/login",
        request=request,
        settings=settings,
        rate_limiter=rate_limiter,
        access_token_service=AccessTokenService(settings),
        routing_service=routing_service,
    )

    assert json.loads(response.body) == {
        "requires_2fa": False,
        "status": "authenticated",
        "auth": "cookie",
        "expires_in": 900,
    }
    set_cookie_headers = _set_cookie_headers(response)
    assert any(
        header.startswith("bp_access_token=") and "HttpOnly" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("bp_refresh_token=") and "HttpOnly" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("bp_csrf_token=") and "HttpOnly" not in header
        for header in set_cookie_headers
    )
    assert rate_limiter.calls == [("public_auth", settings.rate_limit_public_auth_per_minute)]


@pytest.mark.asyncio
async def test_login_2fa_challenge_uses_temporary_httponly_cookie() -> None:
    settings = get_settings()
    rate_limiter = FakeRateLimiter()
    routing_service = FakeRoutingService(
        ProxiedResponse(
            status_code=200,
            body=json.dumps(
                {"requires_2fa": True, "challenge_id": "challenge-123"}
            ).encode("utf-8"),
            headers={"content-type": "application/json"},
        )
    )
    request = _request(
        method="POST",
        path="/v1/auth/login",
        body=json.dumps({"email": "user@example.com", "password": "CorrectPassword!1"}).encode(
            "utf-8"
        ),
        headers={"content-type": "application/json"},
    )

    response = await proxy_request(
        full_path="auth/login",
        request=request,
        settings=settings,
        rate_limiter=rate_limiter,
        access_token_service=AccessTokenService(settings),
        routing_service=routing_service,
    )

    assert json.loads(response.body) == {
        "requires_2fa": True,
        "challenge_id": "challenge-123",
    }
    set_cookie_headers = _set_cookie_headers(response)
    assert any(
        header.startswith("bp_login_challenge=") and "HttpOnly" in header
        for header in set_cookie_headers
    )
    assert all(not header.startswith("bp_refresh_token=") for header in set_cookie_headers)
    assert "x-login-challenge-nonce" in {
        str(key).lower(): value for key, value in routing_service.calls[0]["headers"].items()
    }


@pytest.mark.asyncio
async def test_refresh_uses_refresh_cookie_and_returns_sanitized_cookie_auth_payload() -> None:
    settings = get_settings()
    rate_limiter = FakeRateLimiter()
    routing_service = FakeRoutingService(
        ProxiedResponse(
            status_code=200,
            body=json.dumps(
                {
                    "access_token": "new-access-token",
                    "refresh_token": "new-refresh-token",
                    "expires_in": 900,
                }
            ).encode("utf-8"),
            headers={"content-type": "application/json"},
        )
    )
    request = _request(
        method="POST",
        path="/v1/tokens/refresh",
        body=b"{}",
        headers={
            "content-type": "application/json",
            "cookie": "bp_refresh_token=browser-refresh-token; bp_csrf_token=csrf-123",
            "x-csrf-token": "csrf-123",
        },
    )

    response = await proxy_request(
        full_path="tokens/refresh",
        request=request,
        settings=settings,
        rate_limiter=rate_limiter,
        access_token_service=AccessTokenService(settings),
        routing_service=routing_service,
    )

    forwarded_body = json.loads(routing_service.calls[0]["body"])
    assert forwarded_body == {"refresh_token": "browser-refresh-token"}
    assert json.loads(response.body) == {
        "status": "refreshed",
        "auth": "cookie",
        "expires_in": 900,
    }
    set_cookie_headers = _set_cookie_headers(response)
    assert any(header.startswith("bp_access_token=") for header in set_cookie_headers)
    assert any(header.startswith("bp_refresh_token=") for header in set_cookie_headers)
