from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from smtplib import SMTPException

LOGGER = logging.getLogger(__name__)

_DEFAULT_SMTP_TIMEOUT_SEC = 30


class EmailProvider:
    def __init__(
        self,
        *,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        from_email: str | None,
        require_delivery: bool,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.from_email = from_email
        self.require_delivery = require_delivery

    async def send(self, *, to_email: str, subject: str, body: str) -> None:
        if not self.host or not self.from_email:
            if self.require_delivery:
                raise RuntimeError("Email delivery is not configured")
            LOGGER.warning(
                "email.delivery_skipped",
                extra={"to": to_email, "subject": subject, "reason": "not_configured"},
            )
            return None

        host = self.host
        from_email = self.from_email
        message = EmailMessage()
        message["From"] = from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        def _send() -> None:
            try:
                if self.use_tls and self.port == 465:
                    with smtplib.SMTP_SSL(
                        host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC
                    ) as smtp:
                        if self.username and self.password:
                            smtp.login(self.username, self.password)
                        smtp.send_message(message)
                else:
                    with smtplib.SMTP(host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC) as smtp:
                        smtp.ehlo()
                        if self.use_tls:
                            smtp.starttls()
                            smtp.ehlo()
                        if self.username and self.password:
                            smtp.login(self.username, self.password)
                        smtp.send_message(message)
            except SMTPException as exc:
                LOGGER.exception(
                    "email.smtp_failed",
                    extra={"to": to_email, "host": host, "port": self.port, "error": str(exc)},
                )
                raise
            except OSError as exc:
                LOGGER.exception(
                    "email.smtp_network_failed",
                    extra={"to": to_email, "host": host, "port": self.port, "error": str(exc)},
                )
                raise

        await asyncio.to_thread(_send)
        LOGGER.info("email.sent", extra={"to": to_email, "subject": subject})
