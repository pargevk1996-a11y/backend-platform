from __future__ import annotations

from starlette.responses import Response

from app.core.middleware import apply_no_store_headers, should_disable_caching


def test_should_disable_caching_for_browser_auth_endpoints() -> None:
    assert should_disable_caching("POST", "/v1/auth/login") is True
    assert should_disable_caching("POST", "/v1/tokens/revoke") is True
    assert should_disable_caching("POST", "/v1/two-factor/setup") is True
    assert should_disable_caching("GET", "/ui/") is False


def test_apply_no_store_headers_sets_cache_busting_headers() -> None:
    response = Response()

    apply_no_store_headers(response)

    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert response.headers["Expires"] == "0"
