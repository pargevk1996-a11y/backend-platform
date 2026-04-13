from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository

LOGGER = logging.getLogger("audit")

SENSITIVE_FIELDS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
}


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def _sanitize_payload(
        self,
        payload: dict[str, str | int | bool | None] | None,
    ) -> dict[str, str | int | bool | None]:
        sanitized: dict[str, str | int | bool | None] = {}
        for key, value in (payload or {}).items():
            if key.lower() in SENSITIVE_FIELDS:
                continue
            sanitized[key] = value
        return sanitized

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
        payload: dict[str, str | int | bool | None] | None = None,
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
