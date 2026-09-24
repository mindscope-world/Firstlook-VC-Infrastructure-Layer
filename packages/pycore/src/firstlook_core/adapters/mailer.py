"""Outbound email. SMTP (Mailpit locally) until a provider is chosen."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from ..config import get_settings


class Mailer(Protocol):
    def send(self, to: list[str], subject: str, text: str, sender: str = "firstlook@localhost") -> None: ...


class SmtpMailer:
    def __init__(self, host: str, port: int):
        self.host, self.port = host, port

    def send(self, to: list[str], subject: str, text: str, sender: str = "firstlook@localhost") -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = sender, ", ".join(to), subject
        msg.set_content(text)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(msg)


class MemoryMailer:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, to: list[str], subject: str, text: str, sender: str = "firstlook@localhost") -> None:
        self.sent.append({"to": to, "subject": subject, "text": text, "sender": sender})


@lru_cache
def get_mailer() -> Mailer:
    s = get_settings()
    return SmtpMailer(s.smtp_host, s.smtp_port)
