"""HTML email to text, removing client-marked quoted history."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

# Containers mail clients use to wrap quoted history.
_QUOTE_SELECTORS = [
    "div.gmail_quote",
    "blockquote.gmail_quote",
    "blockquote[type=cite]",
    "div.moz-cite-prefix",
    "div.yahoo_quoted",
    "div#appendonsend",
    "div.protonmail_quote",
]
# Outlook marks the reply header; everything from it onwards is history.
_CUT_FROM_SELECTORS = ["div#divRplyFwdMsg", "div#mail-editor-reference-message-container"]

_BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote", "hr"}


def _to_text(root: Tag) -> str:
    for br in root.find_all("br"):
        br.replace_with("\n")
    for tag in root.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    for li in root.find_all("li"):
        li.insert(0, "- ")
    text = root.get_text()
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _cut_from(marker: Tag) -> None:
    """Remove marker and everything after it in document order."""
    node: Tag | None = marker
    while node is not None and node.name not in ("body", "html", "[document]"):
        for sibling in list(node.next_siblings):
            sibling.extract()
        parent = node.parent
        if node is marker:
            # Outlook often puts an <hr> right before the reply header.
            prev = marker.find_previous_sibling()
            if prev is not None and prev.name == "hr":
                prev.extract()
            marker.extract()
        node = parent


def html_to_text(html: str) -> tuple[str, str]:
    """Return (full_text, text_without_quoted_history)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "title", "meta"]):
        tag.decompose()
    full = _to_text(BeautifulSoup(str(soup), "lxml"))

    for selector in _QUOTE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()
    for selector in _CUT_FROM_SELECTORS:
        marker = soup.select_one(selector)
        if marker is not None:
            _cut_from(marker)
    return full, _to_text(soup)
