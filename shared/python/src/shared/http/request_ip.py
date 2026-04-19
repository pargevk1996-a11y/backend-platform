"""HTTP request helpers shared across FastAPI services.

These utilities avoid a hard Starlette/FastAPI import by treating the request
object structurally: they only look at ``request.client.host`` and
``request.headers``. That keeps ``shared.http`` usable from anything that
provides a similar shape (including test doubles).
"""
from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Protocol


class _ClientLike(Protocol):
    host: str | None


class _RequestLike(Protocol):
    client: _ClientLike | None
    headers: dict[str, str]


def is_trusted_proxy(client_host: str | None, trusted_proxy_ips: list[str] | None) -> bool:
    """Return True iff client_host is covered by trusted_proxy_ips."""
    if not client_host:
        return False
    for trusted in trusted_proxy_ips or []:
        candidate = trusted.strip()
        if not candidate:
            continue
        if candidate == client_host:
            return True
        try:
            client_ip = ip_address(client_host)
            if "/" in candidate:
                if client_ip in ip_network(candidate, strict=False):
                    return True
            elif client_ip == ip_address(candidate):
                return True
        except ValueError:
            continue
    return False


def get_client_ip(request: _RequestLike, trusted_proxy_ips: list[str] | None = None) -> str:
    """Return the client IP, honouring X-Forwarded-For only from trusted proxies.

    The first hop in X-Forwarded-For is returned when present and the immediate
    peer is listed in ``trusted_proxy_ips``. Otherwise the direct peer address
    is used. Returns the literal ``"unknown"`` when neither is available.
    """
    client = getattr(request, "client", None)
    client_host = client.host if client is not None and getattr(client, "host", None) else None
    xff = request.headers.get("x-forwarded-for") if request.headers else None
    if xff and is_trusted_proxy(client_host, trusted_proxy_ips):
        first = xff.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if client_host:
        return client_host
    return "unknown"


def extract_bearer_token(request: _RequestLike) -> str | None:
    """Return the raw bearer token from the Authorization header, or None."""
    headers = getattr(request, "headers", {}) or {}
    authorization = headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    return token or None
