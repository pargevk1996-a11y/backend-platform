from __future__ import annotations

import asyncio
import base64
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import numpy as np
import pyotp
import pytest

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


def _totp_from_setup_qr(qr_png_base64: str) -> pyotp.TOTP:
    if cv2 is None:
        raise RuntimeError("e2e requires opencv-python-headless and numpy (see tests/e2e/requirements.txt)")
    raw = base64.b64decode(qr_png_base64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise AssertionError("failed to decode setup QR image")
    detector = cv2.QRCodeDetector()
    uri, _, _ = detector.detectAndDecode(img)
    if not uri:
        raise AssertionError("no otpauth URI in QR")
    return pyotp.parse_uri(uri)

pytestmark = pytest.mark.e2e


def _base_url() -> str:
    return os.getenv("GATEWAY_BASE_URL", "http://localhost:8000").rstrip("/")


def _strong_password() -> str:
    return "StrongPassword!12345"


def _csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    token = client.cookies.get("bp_csrf_token")
    assert token
    return {"X-CSRF-Token": token}


async def _wait_for_next_totp_code(totp: pyotp.TOTP, *, previous_code: str) -> str:
    deadline = datetime.now(UTC).timestamp() + 35
    while datetime.now(UTC).timestamp() < deadline:
        code = totp.at(for_time=datetime.now(UTC))
        if code != previous_code:
            return code
        await asyncio.sleep(0.5)
    raise AssertionError("Timed out waiting for next TOTP time window")


@pytest.mark.asyncio
async def test_gateway_auth_security_flow() -> None:
    email = f"user-{uuid4().hex}@example.com"
    password = _strong_password()

    async with httpx.AsyncClient(base_url=_base_url(), timeout=20.0) as client:
        register_response = await client.post(
            "/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert register_response.status_code == 201, register_response.text
        register_payload = register_response.json()
        assert register_payload["auth"] == "cookie"
        assert "access_token" not in register_payload
        assert "refresh_token" not in register_payload
        assert client.cookies.get("bp_access_token")
        assert client.cookies.get("bp_refresh_token")

        setup_response = await client.post(
            "/v1/two-factor/setup",
            headers=_csrf_headers(client),
        )
        assert setup_response.status_code == 200, setup_response.text
        setup_payload = setup_response.json()
        assert "secret" not in setup_payload
        assert "provisioning_uri" not in setup_payload
        totp = _totp_from_setup_qr(setup_payload["qr_png_base64"])
        current_code = totp.at(for_time=datetime.now(UTC))
        enable_response = await client.post(
            "/v1/two-factor/enable",
            headers=_csrf_headers(client),
            json={"totp_code": current_code},
        )
        assert enable_response.status_code == 200, enable_response.text
        backup_codes = enable_response.json()["backup_codes"]
        assert isinstance(backup_codes, list) and len(backup_codes) == 10

        logout_response = await client.post(
            "/v1/tokens/revoke",
            headers=_csrf_headers(client),
            json={},
        )
        assert logout_response.status_code == 200, logout_response.text

        login_response = await client.post(
            "/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_response.status_code == 200, login_response.text
        login_payload = login_response.json()
        assert login_payload["requires_2fa"] is True
        assert "tokens" not in login_payload or login_payload["tokens"] is None
        challenge_id = login_payload["challenge_id"]

        verify_code = await _wait_for_next_totp_code(totp, previous_code=current_code)
        login_2fa_response = await client.post(
            "/v1/auth/login/2fa",
            json={"challenge_id": challenge_id, "totp_code": verify_code},
        )
        assert login_2fa_response.status_code == 200, login_2fa_response.text
        token_pair = login_2fa_response.json()
        assert token_pair["auth"] == "cookie"
        assert "access_token" not in token_pair
        assert "refresh_token" not in token_pair
        old_access_cookie = client.cookies.get("bp_access_token")
        rotated_refresh = client.cookies.get("bp_refresh_token")
        assert old_access_cookie
        assert rotated_refresh

        refresh_response = await client.post(
            "/v1/tokens/refresh",
            headers=_csrf_headers(client),
            json={},
        )
        assert refresh_response.status_code == 200, refresh_response.text
        refresh_payload = refresh_response.json()
        assert refresh_payload["auth"] == "cookie"
        newest_refresh = client.cookies.get("bp_refresh_token")
        assert newest_refresh
        assert newest_refresh != rotated_refresh

        reused_response = await client.post(
            "/v1/tokens/refresh",
            json={"refresh_token": rotated_refresh},
        )
        assert reused_response.status_code in {401, 409}, reused_response.text

        revoke_response = await client.post(
            "/v1/tokens/revoke",
            headers=_csrf_headers(client),
            json={},
        )
        assert revoke_response.status_code == 200, revoke_response.text

        post_logout_access = await client.post(
            "/v1/two-factor/setup",
            headers={"Authorization": f"Bearer {old_access_cookie}"},
        )
        assert post_logout_access.status_code == 401, post_logout_access.text

        post_revoke_refresh = await client.post(
            "/v1/tokens/refresh",
            json={"refresh_token": newest_refresh},
        )
        assert post_revoke_refresh.status_code in {401, 409}, post_revoke_refresh.text
