"""Email integrations (SMTP delivery for password reset, etc.)."""

from app.integrations.email.provider import EmailProvider

__all__ = ["EmailProvider"]
