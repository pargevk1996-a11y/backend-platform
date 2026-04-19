from __future__ import annotations

from types import SimpleNamespace

from shared.http import extract_bearer_token, get_client_ip, is_trusted_proxy


def _req(client_host: str | None = None, headers: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        client=SimpleNamespace(host=client_host) if client_host is not None else None,
        headers=headers or {},
    )


def test_is_trusted_proxy_matches_exact_ip() -> None:
    assert is_trusted_proxy("10.0.0.1", ["10.0.0.1"])


def test_is_trusted_proxy_matches_cidr() -> None:
    assert is_trusted_proxy("172.20.5.1", ["172.16.0.0/12"])


def test_is_trusted_proxy_rejects_outside_cidr() -> None:
    assert not is_trusted_proxy("8.8.8.8", ["172.16.0.0/12"])


def test_is_trusted_proxy_empty_list_is_false() -> None:
    assert not is_trusted_proxy("1.2.3.4", [])
    assert not is_trusted_proxy("1.2.3.4", None)


def test_get_client_ip_prefers_trusted_xff() -> None:
    request = _req(
        client_host="172.20.0.5",
        headers={"x-forwarded-for": "203.0.113.9, 172.20.0.4"},
    )
    assert get_client_ip(request, ["172.16.0.0/12"]) == "203.0.113.9"


def test_get_client_ip_ignores_xff_from_untrusted_peer() -> None:
    request = _req(
        client_host="8.8.8.8",
        headers={"x-forwarded-for": "1.2.3.4"},
    )
    assert get_client_ip(request, ["172.16.0.0/12"]) == "8.8.8.8"


def test_get_client_ip_unknown_when_no_client() -> None:
    assert get_client_ip(_req()) == "unknown"


def test_extract_bearer_token_happy_path() -> None:
    request = _req(headers={"authorization": "Bearer abc.def.ghi"})
    assert extract_bearer_token(request) == "abc.def.ghi"


def test_extract_bearer_token_missing_returns_none() -> None:
    assert extract_bearer_token(_req(headers={})) is None


def test_extract_bearer_token_wrong_scheme_returns_none() -> None:
    assert extract_bearer_token(_req(headers={"authorization": "Basic xxx"})) is None
