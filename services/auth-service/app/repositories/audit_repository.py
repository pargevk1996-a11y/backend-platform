from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        outcome: str,
        actor_user_id: UUID | None,
        target_user_id: UUID | None,
        ip_address: str | None,
        user_agent: str | None,
        payload: dict[str, Any],
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            payload=payload,
        )
        session.add(event)
        await session.flush()
        return event
