"""News from RSS feeds: mentions of tracked companies and funding announcements.

Funding headlines ("X raises $3M seed") are also a discovery source: a company
that isn't in the graph yet becomes a sourcing candidate.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from ..model import CompanyProfile, Observation
from ..taxonomy import normalise_stage
from . import USER_AGENT

DEFAULT_FEEDS = [
    "https://techcabal.com/feed/",
    "https://techpoint.africa/feed/",
    "https://disrupt-africa.com/feed/",
    "https://weetracker.com/feed/",
]

_FUNDING = re.compile(
    r"(?P<name>[A-Z][\w&.'\-]*(?:\s+[A-Z][\w&.'\-]*){0,3})\s+"
    r"(?i:raises|secures|closes|lands|bags|nets|announces)\s+"
    r"(?i:a\s+)?(?P<amount>\$\s?[\d.,]*\d(?:\s?(?i:million|m|k|thousand|billion|bn)\b)?)"
    r"(?:\s+(?i:in\s+)?(?P<stage>(?i:pre-seed|seed|series\s+[a-e]))\b)?",
)
_STOP_NAMES = {"The", "This", "Startup", "Company", "Nigerian", "Kenyan", "African", "Fintech", "Report"}


@dataclass
class NewsItem:
    title: str
    url: str
    published_at: datetime
    summary: str
    feed: str


def parse_amount(text: str) -> float | None:
    m = re.search(r"([\d.,]+)\s?(million|m|k|thousand|billion|bn)?", text.lower().replace("$", ""))
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = m.group(2) or ""
    return n * {"million": 1e6, "m": 1e6, "k": 1e3, "thousand": 1e3, "billion": 1e9, "bn": 1e9}.get(unit, 1)


def parse_feed(xml_text: str, feed: str) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            when = datetime.now(UTC)
        summary = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        items.append(NewsItem(title, link, when, re.sub(r"\s+", " ", summary).strip()[:600], feed))
    return items


class NewsSource:
    name = "news"

    def __init__(self, feeds: list[str] | None = None, http: httpx.Client | None = None):
        self.feeds = feeds or DEFAULT_FEEDS
        self.http = http or httpx.Client(
            timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for feed in self.feeds:
            try:
                r = self.http.get(feed)
                r.raise_for_status()
                items += parse_feed(r.text, feed)
            except (httpx.HTTPError, ET.ParseError):
                continue  # one bad feed shouldn't stop the others
        return items

    @staticmethod
    def mentions(items: list[NewsItem], company_names: dict[str, str]) -> dict[str, list[Observation]]:
        """company_names: {company_id: name}. Returns {company_id: observations}."""
        out: dict[str, list[Observation]] = {}
        for cid, name in company_names.items():
            if len(name) < 4:
                continue  # too ambiguous to match in free text
            pattern = re.compile(rf"\b{re.escape(name)}\b", re.I)
            for item in items:
                if pattern.search(item.title) or pattern.search(item.summary):
                    out.setdefault(cid, []).append(
                        Observation(
                            "news_mention",
                            1.0,
                            f"rss:{_host(item.feed)}",
                            url=item.url,
                            observed_at=item.published_at,
                            detail={"title": item.title},
                        )
                    )
        return out

    @staticmethod
    def funding_announcements(items: list[NewsItem]) -> list[tuple[CompanyProfile, Observation]]:
        out = []
        for item in items:
            m = _FUNDING.search(item.title)
            if not m or m.group("name").split()[0] in _STOP_NAMES:
                continue
            amount = parse_amount(m.group("amount"))
            stage = normalise_stage(m.group("stage")) if m.group("stage") else None
            profile = CompanyProfile(
                name=m.group("name").strip(),
                stage=stage,
                last_round_usd=amount,
                last_round_at=item.published_at.date(),
                description=item.summary or None,
                source=f"rss:{_host(item.feed)}",
                source_ref=item.url,
            )
            obs = Observation(
                "funding_round_usd",
                amount or 0.0,
                f"rss:{_host(item.feed)}",
                url=item.url,
                observed_at=item.published_at,
                detail={"title": item.title, "stage": stage},
            )
            out.append((profile, obs))
        return out


def _host(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
