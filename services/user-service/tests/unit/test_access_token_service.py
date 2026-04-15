from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import AccessTokenService, ensure_access_session_active
from app.exceptions.auth import UnauthorizedException
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
    assert str(claims.jti) == payload["jti"]
    assert str(claims.sid) == payload["sid"]


@pytest.mark.asyncio
async def test_decode_access_token_rejects_wrong_type() -> None:
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
