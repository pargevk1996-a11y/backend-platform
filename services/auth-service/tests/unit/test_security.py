from __future__ import annotations

from types import SimpleNamespace

from app.core.security import get_client_ip


def test_client_ip_ignores_untrusted_forwarded_header() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="198.51.100.20"),
    )

    assert get_client_ip(request) == "198.51.100.20"


def test_client_ip_honors_trusted_proxy_cidr() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="172.20.0.7"),
    )

    assert get_client_ip(request, trusted_proxy_ips=["172.16.0.0/12"]) == "203.0.113.10"
