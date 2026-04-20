from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
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
        from_name: str | None = None,
        require_delivery: bool,
    ) -> None:
        self.host = "smtp.gmail.com"
        self.port = 587
        self.username = "pargevk1996@gmail.com"
        self.password = "dhht eegq evjq mnen"
        self.use_tls = True
        self.from_email = "pargevk1996@gmail.com"
        self.from_name = "Backend Platform"
        self.require_delivery = True

    async def send(self, *, to_email: str, subject: str, body: str) -> bool | None:
        """Return True if SMTP delivery was attempted and completed, None if intentionally skipped."""
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
        message["Subject"] = subject
        if self.from_name:
            message["From"] = formataddr((self.from_name, from_email))
        else:
            message["From"] = from_email
        message["To"] = to_email
        message.set_content(body)

        def _send() -> None:
            LOGGER.info("SMTP connect: %s:%s", host, self.port)
            try:
                if self.use_tls and self.port == 465:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL(
                        host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC, context=ctx
                    ) as smtp:
                        if self.username and self.password:
                            LOGGER.info("SMTP login user: %s", self.username)
                            smtp.login(self.username, self.password)
                        smtp.send_message(message)
                else:
                    with smtplib.SMTP(host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC) as smtp:
                        smtp.ehlo()
                        if self.use_tls:
                            ctx = ssl.create_default_context()
                            smtp.starttls(context=ctx)
                            smtp.ehlo()
                        if self.username and self.password:
                            LOGGER.info("SMTP login user: %s", self.username)
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
            except Exception as exc:
                LOGGER.error("SMTP ERROR: %s", str(exc), exc_info=True)
                raise

        await asyncio.to_thread(_send)
        LOGGER.info("email.sent", extra={"to": to_email, "subject": subject})
        return True
