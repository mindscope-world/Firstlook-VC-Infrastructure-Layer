from .html import html_to_text
from .mime import ParsedAddress, ParsedAttachment, ParsedEmail, parse_rfc822
from .quotes import strip_quoted
from .signature import parse_signature, split_signature

__all__ = [
    "ParsedAddress",
    "ParsedAttachment",
    "ParsedEmail",
    "clean_body",
    "html_to_text",
    "parse_rfc822",
    "parse_signature",
    "split_signature",
    "strip_quoted",
]


def clean_body(email: ParsedEmail) -> tuple[str, str, str | None]:
    """Return (full_text, cleaned_text, signature) for an email.

    cleaned_text is the new content only: quoted replies and the signature
    removed. HTML-aware quote removal runs first when there is an HTML part,
    then text-level heuristics catch what the markup didn't mark.
    """
    if email.html:
        full, unquoted = html_to_text(email.html)
        if email.text and len(unquoted.strip()) == 0:
            unquoted = email.text
    else:
        full = email.text or ""
        unquoted = full
    unquoted = strip_quoted(unquoted)
    body, signature = split_signature(unquoted)
    return full.strip(), body.strip(), signature
