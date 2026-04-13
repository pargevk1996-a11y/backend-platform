from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.core.security import AccessTokenService, is_public_endpoint
from app.exceptions.gateway import UnauthorizedException


def _generate_rsa_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
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
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        "iat": datetime.now(tz=timezone.utc),
        "nbf": datetime.now(tz=timezone.utc),
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
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        "iat": datetime.now(tz=timezone.utc),
        "nbf": datetime.now(tz=timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_public_key_value, algorithm=settings.jwt_algorithm)

    with pytest.raises(UnauthorizedException):
        service.decode_access_token(token)


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
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        "iat": datetime.now(tz=timezone.utc),
        "nbf": datetime.now(tz=timezone.utc),
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")

    claims = service.decode_access_token(token)
    assert str(claims.sub) == payload["sub"]
    assert str(claims.jti) == payload["jti"]
    assert str(claims.sid) == payload["sid"]


@pytest.mark.asyncio
async def test_public_endpoint_detection() -> None:
    assert is_public_endpoint("POST", "/v1/auth/login") is True
    assert is_public_endpoint("GET", "/v1/users/me") is False
