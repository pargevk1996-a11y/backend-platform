from __future__ import annotations

from fastapi import Request

from app.exceptions.auth import UnauthorizedException


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise UnauthorizedException("Missing bearer token")
    return token
