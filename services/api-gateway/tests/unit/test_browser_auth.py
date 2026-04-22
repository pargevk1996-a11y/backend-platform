from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def gateway_client() -> Iterator[TestClient]:
    """StaticFiles uses cwd-relative paths; TestClient must run lifespan (Redis, routing)."""
    prev = os.getcwd()
    os.chdir(SERVICE_ROOT)
    try:
        from app.main import app

        with TestClient(app) as client:
            yield client
    finally:
        os.chdir(prev)


def test_browser_refresh_without_cookie_returns_401(gateway_client: TestClient) -> None:
    res = gateway_client.post("/v1/browser-auth/refresh", json={})
    assert res.status_code == 401
    body = res.json()
    assert body.get("message") == "Missing refresh cookie"
    assert body.get("error_code") == "HTTP_ERROR"


def test_browser_revoke_without_cookie_returns_401(gateway_client: TestClient) -> None:
    res = gateway_client.post("/v1/browser-auth/revoke", json={})
    assert res.status_code == 401
    body = res.json()
    assert body.get("message") == "Missing refresh cookie"


def test_browser_refresh_without_cookie_logs_diagnostic(
    gateway_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.api.v1.browser_auth"):
        gateway_client.post("/v1/browser-auth/refresh", json={})
    assert any(
        getattr(r, "message", "") == "browser_auth_missing_refresh_cookie" for r in caplog.records
    ), "expected structured info log for ops / log aggregation"
