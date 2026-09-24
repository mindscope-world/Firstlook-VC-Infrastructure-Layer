"""Text-level removal of quoted reply history."""

from __future__ import annotations

import re

# Reply headers in common clients and languages. Each marks the start of history.
_REPLY_HEADERS = [
    re.compile(r"^On\b.{0,300}\bwrote:\s*$", re.I | re.S),
    re.compile(r"^Le\b.{0,300}\ba écrit\s*:\s*$", re.I | re.S),
    re.compile(r"^Am\b.{0,300}\bschrieb.{0,80}:\s*$", re.I | re.S),
    re.compile(r"^El\b.{0,300}\bescribió:\s*$", re.I | re.S),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.I),
    re.compile(r"^_{20,}\s*$"),
]
_OUTLOOK_FROM = re.compile(r"^\*?From:\*?\s+.+", re.I)
_OUTLOOK_NEXT = re.compile(r"^\*?(Sent|Date|To|Subject):\*?\s", re.I)
_FORWARD = re.compile(r"^-{3,}\s*Forwarded message\s*-{3,}|^Begin forwarded message:", re.I)


def _is_reply_header(lines: list[str], i: int) -> bool:
    line = lines[i].strip()
    # "On Mon, ... wrote:" is often wrapped over two lines.
    joined = " ".join(x.strip() for x in lines[i : i + 2])
    for pattern in _REPLY_HEADERS:
        if pattern.match(line) or (
            line.lower().startswith(("on ", "le ", "am ", "el ")) and pattern.match(joined)
        ):
            return True
    if _OUTLOOK_FROM.match(line):
        following = [x.strip() for x in lines[i + 1 : i + 5] if x.strip()]
        return any(_OUTLOOK_NEXT.match(x) for x in following[:3])
    return False


def strip_quoted(text: str) -> str:
    """Cut the text at the first reply header, and drop '>'-quoted lines.

    Forwarded messages are kept: a forward's content is usually the point of
    the email (an intro, a deck), not history.
    """
    lines = text.splitlines()
    out: list[str] = []
    in_forward = False
    for i, line in enumerate(lines):
        if _FORWARD.match(line.strip()):
            in_forward = True
        if not in_forward and _is_reply_header(lines, i):
            break
        if line.lstrip().startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).rstrip()
