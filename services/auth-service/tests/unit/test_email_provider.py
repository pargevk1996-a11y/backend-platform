from __future__ import annotations

import logging

import pytest
from app.integrations.email.provider import EmailProvider


@pytest.mark.asyncio
async def test_email_provider_runs_smtp_send(monkeypatch: pytest.MonkeyPatch) -> None:
    sent_messages: list[dict[str, object]] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *args: object, **kwargs: object) -> None:
            self.host = host
            self.port = port
            self.login_calls: list[tuple[str, str]] = []

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            self.login_calls.append((username, password))

        def send_message(self, message) -> None:
            sent_messages.append(
                {
                    "host": self.host,
                    "port": self.port,
                    "to": message["To"],
                    "subject": message["Subject"],
                    "login_calls": self.login_calls,
                }
            )

    monkeypatch.setattr("app.integrations.email.provider.smtplib.SMTP", FakeSMTP)

    provider = EmailProvider(
        host="smtp.example.com",
        port=2525,
        username="mailer",
        password="secret",
        use_tls=False,
        from_email="security@example.com",
        require_delivery=True,
    )

    await provider.send(to_email="user@example.com", subject="Reset", body="Code: 123456")

    assert sent_messages == [
        {
            "host": "smtp.example.com",
            "port": 2525,
            "to": "user@example.com",
            "subject": "Reset",
            "login_calls": [("mailer", "secret")],
        }
    ]


@pytest.mark.asyncio
async def test_email_provider_uses_starttls_for_tls_non_ssl_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[dict[str, object]] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *args: object, **kwargs: object) -> None:
            self.host = host
            self.port = port
            self.starttls_called = False

        def __enter__(self) -> FakeSMTP:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def ehlo(self) -> None:
            return None

        def starttls(self) -> None:
            self.starttls_called = True

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message) -> None:
            sent_messages.append(
                {
                    "host": self.host,
                    "port": self.port,
                    "to": message["To"],
                    "starttls_called": self.starttls_called,
                }
            )

    monkeypatch.setattr("app.integrations.email.provider.smtplib.SMTP", FakeSMTP)

    provider = EmailProvider(
        host="smtp.example.com",
        port=587,
        username="mailer",
        password="secret",
        use_tls=True,
        from_email="security@example.com",
        require_delivery=True,
    )

    await provider.send(to_email="user@example.com", subject="Reset", body="Code: 123456")

    assert sent_messages == [
        {
            "host": "smtp.example.com",
            "port": 587,
            "to": "user@example.com",
            "starttls_called": True,
        }
    ]


@pytest.mark.asyncio
async def test_email_provider_uses_smtp_ssl_for_implicit_tls_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent_messages: list[dict[str, object]] = []

    class FakeSMTPSSL:
        def __init__(self, host: str, port: int, *args: object, **kwargs: object) -> None:
            self.host = host
            self.port = port

        def __enter__(self) -> FakeSMTPSSL:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def login(self, username: str, password: str) -> None:
            return None

        def send_message(self, message) -> None:
            sent_messages.append(
                {
                    "host": self.host,
                    "port": self.port,
                    "to": message["To"],
                }
            )

    monkeypatch.setattr("app.integrations.email.provider.smtplib.SMTP_SSL", FakeSMTPSSL)

    provider = EmailProvider(
        host="smtp.example.com",
        port=465,
        username="mailer",
        password="secret",
        use_tls=True,
        from_email="security@example.com",
        require_delivery=True,
    )

    await provider.send(to_email="user@example.com", subject="Reset", body="Code: 123456")

    assert sent_messages == [
        {
            "host": "smtp.example.com",
            "port": 465,
            "to": "user@example.com",
        }
    ]


@pytest.mark.asyncio
async def test_email_provider_does_not_log_body_when_delivery_is_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = EmailProvider(
        host=None,
        port=587,
        username=None,
        password=None,
        use_tls=True,
        from_email=None,
        require_delivery=False,
    )

    with caplog.at_level(logging.WARNING, logger="app.integrations.email.provider"):
        await provider.send(
            to_email="user@example.com",
            subject="Reset",
            body="Reset code: 123456",
        )

    assert "email.delivery_skipped" in caplog.text
    assert "123456" not in caplog.text
