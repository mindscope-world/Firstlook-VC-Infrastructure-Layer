"""Signature detection and parsing.

Signatures are split from the body (so extraction reads only new content) and
parsed for enrichment: a founder's title and phone number usually live there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DELIMITER = re.compile(r"^--\s?$")
_MOBILE = re.compile(
    r"^(Sent from my \w+|Sent from (Outlook|Mail|Yahoo Mail)|Get Outlook for \w+|Sent via .+)\b.*$", re.I
)
_SIGN_OFF = re.compile(
    r"^(best|best regards|kind regards|warm regards|warmly|regards|thanks|thank you|many thanks|thanks so much|"
    r"cheers|sincerely|yours|all the best|talk soon|asante|br)[,.!]?\s*$",
    re.I,
)
_PHONE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
_URL = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?", re.I)
_TITLE_WORDS = re.compile(
    r"\b(ceo|cto|coo|cfo|cpo|founder|co-founder|cofounder|partner|principal|associate|analyst|director|manager|"
    r"head|vp|vice president|president|chair|engineer|lead|investor|advisor|general counsel|md|managing)\b",
    re.I,
)


def split_signature(text: str, max_lines: int = 12) -> tuple[str, str | None]:
    """Return (body, signature). The signature is None if none was found."""
    lines = text.rstrip().splitlines()
    if not lines:
        return text, None

    for i, line in enumerate(lines):
        if _DELIMITER.match(line):
            return "\n".join(lines[:i]).rstrip(), "\n".join(lines[i + 1 :]).strip() or None

    # Mobile client footers are always signature.
    while lines and _MOBILE.match(lines[-1].strip()):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()

    start = max(0, len(lines) - max_lines)
    for i in range(len(lines) - 1, start - 1, -1):
        if _SIGN_OFF.match(lines[i].strip()):
            tail = [x for x in lines[i + 1 :] if x.strip()]
            # A sign-off followed by a long paragraph is not a signature.
            if all(len(x) <= 80 for x in tail) and len(tail) <= 8:
                return "\n".join(lines[:i]).rstrip(), "\n".join(lines[i:]).strip()
    return "\n".join(lines).rstrip(), None


@dataclass
class SignatureInfo:
    name: str | None = None
    title: str | None = None
    company: str | None = None
    phones: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    linkedin: str | None = None


def parse_signature(signature: str, sender_name: str | None = None) -> SignatureInfo:
    info = SignatureInfo()
    lines = [x.strip() for x in signature.splitlines() if x.strip()]
    lines = [x for x in lines if not _SIGN_OFF.match(x)]
    for line in lines:
        for m in _PHONE.findall(line):
            digits = re.sub(r"\D", "", m)
            if 9 <= len(digits) <= 15:
                info.phones.append(m.strip())
        for m in _URL.findall(line):
            if "@" in line and m in line.split("@", 1)[1]:
                continue  # the domain part of an email address
            if "linkedin.com" in m.lower():
                info.linkedin = m if m.startswith("http") else f"https://{m}"
            elif "." in m and not re.fullmatch(r"[\d.]+", m):
                info.urls.append(m)

    text_lines = [x for x in lines if not _PHONE.fullmatch(x) and "@" not in x and not _URL.fullmatch(x)]
    if text_lines:
        first = text_lines[0]
        if (
            sender_name
            and first.lower().startswith(sender_name.split()[0].lower())
            or not _TITLE_WORDS.search(first)
            and len(first.split()) <= 4
        ):
            info.name = first
            text_lines = text_lines[1:]
    for line in text_lines[:3]:
        if _TITLE_WORDS.search(line):
            # "CEO, Acme" / "CEO | Acme" / "CEO at Acme"
            parts = re.split(r"\s*(?:,|\||·|•| at | @ )\s*", line, maxsplit=1)
            info.title = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                info.company = parts[1].strip()
            break
    return info
