from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class CompanyProfile:
    """What a source knows about a company. Only non-None fields are applied."""

    name: str
    domain: str | None = None
    description: str | None = None
    sectors: list[str] = field(default_factory=list)
    stage: str | None = None
    country: str | None = None
    founded_year: int | None = None
    headcount: int | None = None
    total_raised_usd: float | None = None
    last_round_usd: float | None = None
    last_round_at: date | None = None
    github_org: str | None = None
    jobs_board: str | None = None
    registry_id: str | None = None
    source: str = ""  # vendor:<name>, registry:<name>, rss:<feed>
    source_ref: str | None = None  # the source's own id / URL
    founders: list[dict[str, str]] = field(default_factory=list)  # [{"name", "email", "title"}]


@dataclass
class Observation:
    signal: str
    value: float
    source: str
    url: str = ""
    observed_at: datetime | None = None
    detail: dict[str, Any] = field(default_factory=dict)
