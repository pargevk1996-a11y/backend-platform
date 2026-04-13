from __future__ import annotations


class EmailProvider:
    async def send(self, *, to_email: str, subject: str, body: str) -> None:
        # Intentionally left as integration contract. Real implementation should be injected.
        _ = (to_email, subject, body)
        return None
