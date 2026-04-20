import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

LOGGER = logging.getLogger(__name__)
_DEFAULT_SMTP_TIMEOUT_SEC = 30


class EmailProvider:
    def __init__(
        self,
        host: str | None,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        from_email: str | None,
        from_name: str | None = None,
        require_delivery: bool = True,
    ) -> None:
        self.host = (host or "").strip() or None
        self.port = port
        self.username = (username or "").strip() or (from_email or "").strip() or None
        self.password = password
        self.use_tls = use_tls
        self.from_email = (from_email or "").strip() or None
        self.from_name = (from_name or "").strip() or None
        self.require_delivery = require_delivery

    async def send(self, to_email: str, subject: str, body: str) -> None:
        if not self.host or not self.from_email:
            LOGGER.warning("SMTP delivery skipped: provider is not configured")
            if self.require_delivery:
                raise RuntimeError("SMTP provider is not configured")
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = (
            formataddr((self.from_name, self.from_email))
            if self.from_name
            else self.from_email
        )
        message["To"] = to_email
        message.set_content(body)

        def _send() -> None:
            LOGGER.info("SMTP connect: %s:%s", self.host, self.port)
            try:
                with smtplib.SMTP(self.host, self.port, timeout=_DEFAULT_SMTP_TIMEOUT_SEC) as smtp:
                    smtp.ehlo()
                    if self.use_tls:
                        ctx = ssl.create_default_context()
                        smtp.starttls(context=ctx)
                        smtp.ehlo()

                    if self.username and self.password:
                        smtp.login(self.username, self.password)

                    smtp.send_message(message)

            except Exception:
                LOGGER.exception("SMTP ERROR")
                if self.require_delivery:
                    raise

        await asyncio.to_thread(_send)
