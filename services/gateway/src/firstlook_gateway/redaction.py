"""PII redaction applied to prompts before they leave the platform.

Names and email addresses are kept: relationship intelligence needs them.
What is removed is data no task needs and that would be damaging if logged by
a provider: payment cards, bank accounts, government IDs, and credentials.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")),
    ("us_ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("kra_pin", re.compile(r"\b[AP]\d{9}[A-Z]\b")),
    ("credential", re.compile(r"(?i)\b(password|passcode|api[_ -]?key|secret)\s*[:=]\s*\S+")),
]
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}

    def card(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            counts["card"] = counts.get("card", 0) + 1
            return "[REDACTED:card]"
        return m.group(0)

    text = _CARD.sub(card, text)
    for kind, pattern in _PATTERNS:
        text, n = pattern.subn(f"[REDACTED:{kind}]", text)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return text, counts
