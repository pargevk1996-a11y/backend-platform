"""SMTP email delivery.

Values are built in ``get_email_provider`` from ``Settings``, which reads
``services/auth-service/.env`` (and process env overrides), not this module directly.
"""

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
        self.host = (host or "").strip() or None
        self.port = port
        self.from_email = (from_email or "").strip() or None
        # Username defaults to From when only FROM is set in env (e.g. Gmail).
        self.username = (username or "").strip() or self.from_email or None
        self.password = (password or "").strip() or None
        self.use_tls = use_tls
        self.from_name = (from_name or "").strip() or None
        self.require_delivery = require_delivery

    def _missing_for_delivery(self) -> bool:
        return not self.host or not self.from_email or not self.password

    async def send(self, *, to_email: str, subject: str, body: str) -> bool | None:
        """True after successful SMTP send; None if delivery was intentionally skipped."""
        if self.require_delivery and self._missing_for_delivery():
            raise RuntimeError("Email delivery is not configured")

        if not self.host or not self.from_email:
            LOGGER.warning(
                "email.delivery_skipped",
                extra={"to": to_email, "subject": subject, "reason": "not_configured"},
            )
            return None

        if not self.password:
            LOGGER.warning(
                "email.delivery_skipped",
                extra={"to": to_email, "subject": subject, "reason": "missing_password"},
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
            LOGGER.info("SMTP connect", extra={"host": host, "port": self.port})
            try:
                if self.use_tls and self.port == 465:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL(
                        host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC, context=ctx
                    ) as smtp:
                        # username/password checked before _send(); login identity may match From.
                        uname, pwd = self.username, self.password
                        LOGGER.info("SMTP login", extra={"username": uname})
                        smtp.login(uname, pwd)
                        smtp.send_message(message)
                        LOGGER.info(
                            "SMTP send",
                            extra={"to": to_email, "subject": subject},
                        )
                else:
                    with smtplib.SMTP(host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC) as smtp:
                        smtp.ehlo()
                        if self.use_tls:
                            ctx = ssl.create_default_context()
                            smtp.starttls(context=ctx)
                            smtp.ehlo()
                        uname, pwd = self.username, self.password
                        LOGGER.info("SMTP login", extra={"username": uname})
                        smtp.login(uname, pwd)
                        smtp.send_message(message)
                        LOGGER.info(
                            "SMTP send",
                            extra={"to": to_email, "subject": subject},
                        )
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
