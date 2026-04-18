from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository

LOGGER = logging.getLogger("audit")

SENSITIVE_FIELDS = {
    "password",
    "password_hash",
    "access_token",
    "refresh_token",
    "authorization",
    "totp_code",
    "backup_code",
    "backup_codes",
    "secret",
    "encrypted_secret",
    "manual_entry_key",
    "provisioning_uri",
    "otpauth_url",
    "qr_png_base64",
    "private_key",
    "token",
}


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def _sanitize_payload(
        self,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in (payload or {}).items():
            if key.lower() in SENSITIVE_FIELDS:
                continue
            sanitized[key] = self._sanitize_value(value)
        return sanitized

    def _sanitize_value(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for key, inner_value in value.items():
                key_str = str(key)
                if key_str.lower() in SENSITIVE_FIELDS:
                    continue
                sanitized[key_str] = self._sanitize_value(inner_value)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_value(item) for item in value]
        return value

    async def log_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        outcome: str,
        actor_user_id: UUID | None,
        target_user_id: UUID | None,
        ip_address: str | None,
        user_agent: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        safe_payload = self._sanitize_payload(payload)
        await self.repository.create(
            session,
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=safe_payload,
        )
        LOGGER.info(
            "security_event",
            extra={
                "event_type": event_type,
                "outcome": outcome,
                "actor_user_id": str(actor_user_id) if actor_user_id else None,
                "target_user_id": str(target_user_id) if target_user_id else None,
                "ip_address": ip_address,
            },
        )
