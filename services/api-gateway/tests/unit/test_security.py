from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import (
    AccessTokenService,
    ensure_access_session_active,
    get_client_ip,
    is_public_endpoint,
)
from app.exceptions.gateway import UnauthorizedException
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


@pytest.mark.asyncio
async def test_decode_access_token_success() -> None:
    settings = get_settings()
    service = AccessTokenService(settings)

    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "sid": str(uuid4()),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=10),
        "iat": datetime.now(tz=UTC),
        "nbf": datetime.now(tz=UTC),
    }
    token = jwt.encode(payload, settings.jwt_public_key_value, algorithm=settings.jwt_algorithm)

    claims = service.decode_access_token(token)
    assert str(claims.sub) == payload["sub"]


@pytest.mark.asyncio
async def test_decode_access_token_rejects_invalid_type() -> None:
    settings = get_settings()
    service = AccessTokenService(settings)

    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "sid": str(uuid4()),
        "type": "refresh",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=10),
        "iat": datetime.now(tz=UTC),
        "nbf": datetime.now(tz=UTC),
    }
    token = jwt.encode(payload, settings.jwt_public_key_value, algorithm=settings.jwt_algorithm)

    with pytest.raises(UnauthorizedException):
        service.decode_access_token(token)


@pytest.mark.asyncio
async def test_decode_access_token_requires_temporal_claims() -> None:
    settings = get_settings()
    service = AccessTokenService(settings)

    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "sid": str(uuid4()),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=10),
    }
    token = jwt.encode(payload, settings.jwt_public_key_value, algorithm=settings.jwt_algorithm)

    with pytest.raises(UnauthorizedException):
        service.decode_access_token(token)


@pytest.mark.asyncio
async def test_access_session_revocation_marker_rejects_token() -> None:
    class FakeRedis:
        async def exists(self, key: str) -> int:
            assert key.startswith("access_session_revoked:")
            return 1

    with pytest.raises(UnauthorizedException):
        await ensure_access_session_active(FakeRedis(), uuid4())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_decode_access_token_rs256_success() -> None:
    private_key, public_key = _generate_rsa_keypair()
    os.environ["JWT_ALGORITHM"] = "RS256"
    os.environ["JWT_PUBLIC_KEY"] = public_key
    get_settings.cache_clear()

    settings = get_settings()
    service = AccessTokenService(settings)

    payload = {
        "sub": str(uuid4()),
        "jti": str(uuid4()),
        "sid": str(uuid4()),
        "type": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "exp": datetime.now(tz=UTC) + timedelta(minutes=10),
        "iat": datetime.now(tz=UTC),
        "nbf": datetime.now(tz=UTC),
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")

    claims = service.decode_access_token(token)
    assert str(claims.sub) == payload["sub"]
    assert str(claims.jti) == payload["jti"]
    assert str(claims.sid) == payload["sid"]


@pytest.mark.asyncio
async def test_public_endpoint_detection() -> None:
    assert is_public_endpoint("POST", "/v1/auth/login") is True
    assert is_public_endpoint("POST", "/v1/browser-auth/refresh") is True
    assert is_public_endpoint("GET", "/v1/users/me") is False


def test_client_ip_ignores_untrusted_forwarded_header() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="198.51.100.20"),
    )

    assert get_client_ip(request) == "198.51.100.20"


def test_client_ip_honors_trusted_proxy_forwarded_header() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10, 198.51.100.20"},
        client=SimpleNamespace(host="10.0.0.10"),
    )

    assert get_client_ip(request, trusted_proxy_ips=["10.0.0.10"]) == "203.0.113.10"


def test_client_ip_honors_trusted_proxy_cidr() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="172.20.0.7"),
    )

    assert get_client_ip(request, trusted_proxy_ips=["172.16.0.0/12"]) == "203.0.113.10"


def test_client_ip_trusted_list_empty_never_uses_xff() -> None:
    """Explicit empty trusted list — same as no trust: never take client IP from XFF."""
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.18.0.99"},
        client=SimpleNamespace(host="10.0.0.50"),
    )

    assert get_client_ip(request, trusted_proxy_ips=[]) == "10.0.0.50"


def test_client_ip_takes_first_hop_in_xff_chain() -> None:
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.18.0.1, 198.18.0.2"},
        client=SimpleNamespace(host="10.0.0.10"),
    )

    assert get_client_ip(request, trusted_proxy_ips=["10.0.0.10"]) == "198.18.0.1"
