from __future__ import annotations

import pytest
from app.services.audit_service import AuditService


class FakeAuditRepository:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def create(self, session, **kwargs):
        _ = session
        self.payloads.append(kwargs["payload"])
        return None


@pytest.mark.asyncio
async def test_audit_service_removes_sensitive_fields() -> None:
    repository = FakeAuditRepository()
    service = AuditService(repository)

    await service.log_event(
        None,
        event_type="test.event",
        outcome="success",
        actor_user_id=None,
        target_user_id=None,
        ip_address="127.0.0.1",
        user_agent="pytest",
        payload={
            "email": "user@example.com",
            "password": "secret",
            "access_token": "token",
            "totp_code": "123456",
            "is_admin": False,
            "nested": {
                "authorization": "Bearer secret",
                "meta": {"password_hash": "hidden", "region": "eu"},
            },
        },
    )

    saved = repository.payloads[0]
    assert "email" in saved
    assert "is_admin" in saved
    assert "password" not in saved
    assert "access_token" not in saved
    assert "totp_code" not in saved
    nested = saved["nested"]
    assert isinstance(nested, dict)
    assert "authorization" not in nested
    meta = nested["meta"]
    assert isinstance(meta, dict)
    assert "password_hash" not in meta
