from __future__ import annotations

from starlette.responses import Response

from app.core.middleware import apply_no_store_headers, should_disable_caching


def test_should_disable_caching_for_auth_sensitive_endpoints() -> None:
    assert should_disable_caching("POST", "/v1/auth/login") is True
    assert should_disable_caching("POST", "/v1/tokens/refresh") is True
    assert should_disable_caching("POST", "/v1/two-factor/backup-codes/regenerate") is True
    assert should_disable_caching("GET", "/v1/health/live") is False
    assert should_disable_caching("POST", "/v1/users/me") is False


def test_apply_no_store_headers_sets_cache_busting_headers() -> None:
    response = Response()

    apply_no_store_headers(response)

    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Expires"] == "0"
