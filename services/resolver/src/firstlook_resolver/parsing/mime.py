"""RFC 822 / MIME parsing into a structure the pipeline can use."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime


@dataclass(frozen=True)
class ParsedAddress:
    name: str | None
    email: str


@dataclass
class ParsedAttachment:
    filename: str | None
    content_type: str
    data: bytes
    inline: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


@dataclass
class ParsedEmail:
    message_id: str
    subject: str
    date: datetime
    from_: ParsedAddress | None
    to: list[ParsedAddress] = field(default_factory=list)
    cc: list[ParsedAddress] = field(default_factory=list)
    bcc: list[ParsedAddress] = field(default_factory=list)
    reply_to: list[ParsedAddress] = field(default_factory=list)
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    text: str | None = None
    html: str | None = None
    attachments: list[ParsedAttachment] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def thread_key(self) -> str:
        """Root of the reply chain: first References entry, else In-Reply-To, else self."""
        if self.references:
            return self.references[0]
        return self.in_reply_to or self.message_id

    @property
    def participants(self) -> list[tuple[str, ParsedAddress]]:
        out: list[tuple[str, ParsedAddress]] = []
        if self.from_:
            out.append(("from", self.from_))
        out += [("to", a) for a in self.to] + [("cc", a) for a in self.cc] + [("bcc", a) for a in self.bcc]
        return out


_MSGID = re.compile(r"<[^<>\s]+>")


def _addresses(values: list[str]) -> list[ParsedAddress]:
    out = []
    for name, addr in getaddresses([str(v) for v in values]):
        addr = addr.strip().lower()
        if "@" in addr:
            out.append(ParsedAddress(name.strip().strip('"') or None, addr))
    return out


def _decode_part(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError):
        payload = part.get_payload(decode=True) or b""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def parse_rfc822(raw: bytes) -> ParsedEmail:
    msg: EmailMessage = message_from_bytes(raw, policy=policy.default)  # type: ignore[assignment]

    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        # Some systems omit Message-ID; derive a stable one from the bytes.
        message_id = f"<sha256-{hashlib.sha256(raw).hexdigest()}@firstlook.local>"

    try:
        date = parsedate_to_datetime(msg["Date"]) if msg["Date"] else datetime.now(UTC)
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        date = datetime.now(UTC)

    text = html = None
    body = msg.get_body(preferencelist=("plain",))
    if body is not None:
        text = _decode_part(body)
    body = msg.get_body(preferencelist=("html",))
    if body is not None:
        html = _decode_part(body)

    attachments: list[ParsedAttachment] = []
    body_parts = {id(p) for p in (msg.get_body(("plain",)), msg.get_body(("html",))) if p is not None}
    for part in msg.walk():
        if part.is_multipart() or id(part) in body_parts:
            continue
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition in ("attachment", "inline") and (filename or disposition == "attachment"):
            data = part.get_payload(decode=True) or b""
            attachments.append(
                ParsedAttachment(filename, part.get_content_type(), data, inline=disposition == "inline")
            )

    from_list = _addresses(msg.get_all("From", []))
    references = _MSGID.findall(msg.get("References", "") or "")
    in_reply_to = _MSGID.findall(msg.get("In-Reply-To", "") or "")

    return ParsedEmail(
        message_id=message_id,
        subject=str(msg.get("Subject", "") or "").strip(),
        date=date,
        from_=from_list[0] if from_list else None,
        to=_addresses(msg.get_all("To", [])),
        cc=_addresses(msg.get_all("Cc", [])),
        bcc=_addresses(msg.get_all("Bcc", [])),
        reply_to=_addresses(msg.get_all("Reply-To", [])),
        in_reply_to=in_reply_to[0] if in_reply_to else None,
        references=references,
        text=text,
        html=html,
        attachments=attachments,
        headers={
            k: str(v)
            for k, v in msg.items()
            if k.lower() in {"list-unsubscribe", "auto-submitted", "precedence"}
        },
    )
