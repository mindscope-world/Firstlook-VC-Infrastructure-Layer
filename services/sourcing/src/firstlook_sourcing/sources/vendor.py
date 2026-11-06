"""Licensed company-data vendors (Crunchbase, Dealroom, Harmonic, Briter, ...).

The first vendor isn't chosen yet (plan §12, question 3), so this module
defines the interface the ranker depends on and a sandbox implementation
backed by a JSON file shaped like a typical vendor export. Adding the real
vendor means writing one class with `search` and `lookup`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from ..model import CompanyProfile, Observation
from ..taxonomy import expand_geographies, normalise_country, normalise_sectors, normalise_stage


@dataclass
class VendorQuery:
    sectors: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)  # regions or ISO codes
    limit: int = 200


@dataclass
class VendorRecord:
    profile: CompanyProfile
    observations: list[Observation]
    raw: dict[str, Any]


class VendorSource(Protocol):
    name: str

    def search(self, query: VendorQuery) -> list[VendorRecord]: ...

    def lookup(self, domain: str) -> VendorRecord | None: ...


def _announced(value: str | None) -> datetime | None:
    """A round is observed when it was announced, not when we fetched it."""
    return datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC) if value else None


def _record(raw: dict[str, Any], source: str) -> VendorRecord:
    rounds = sorted(raw.get("funding_rounds", []), key=lambda r: r.get("announced_on", ""))
    last = rounds[-1] if rounds else {}
    profile = CompanyProfile(
        name=raw["name"],
        domain=raw.get("domain"),
        description=raw.get("short_description") or raw.get("description"),
        sectors=normalise_sectors(raw.get("categories", [])),
        stage=normalise_stage(raw.get("last_funding_type") or last.get("type")),
        country=normalise_country(raw.get("country_code") or raw.get("country")),
        founded_year=int(raw["founded_on"][:4]) if raw.get("founded_on") else None,
        headcount=raw.get("employee_count"),
        total_raised_usd=raw.get("total_funding_usd"),
        last_round_usd=last.get("money_raised_usd"),
        last_round_at=date.fromisoformat(last["announced_on"]) if last.get("announced_on") else None,
        github_org=raw.get("github_org"),
        jobs_board=raw.get("jobs_board"),
        source=source,
        source_ref=str(raw.get("id") or raw.get("domain") or raw["name"]),
        founders=[
            {"name": f.get("name", ""), "email": f.get("email", ""), "title": f.get("title", "Founder")}
            for f in raw.get("founders", [])
        ],
    )
    observations = [
        Observation(
            "funding_round_usd",
            float(r["money_raised_usd"]),
            source,
            url=r.get("source_url", ""),
            observed_at=_announced(r.get("announced_on")),
            detail={"type": r.get("type"), "announced_on": r.get("announced_on")},
        )
        for r in rounds
        if r.get("money_raised_usd")
    ]
    if raw.get("employee_count") is not None:
        observations.append(Observation("headcount", float(raw["employee_count"]), source))
    if raw.get("web_visits_monthly") is not None:
        observations.append(Observation("web_visits_monthly", float(raw["web_visits_monthly"]), source))
    return VendorRecord(profile, observations, raw)


class SandboxVendor:
    """Vendor stand-in reading a JSON export (list of company objects)."""

    def __init__(self, path: Path, name: str = "sandbox"):
        self.name = name
        self.source = f"vendor:{name}"
        self._rows: list[dict[str, Any]] = json.loads(Path(path).read_text())

    def _matches(self, rec: VendorRecord, q: VendorQuery) -> bool:
        p = rec.profile
        if q.sectors and not set(p.sectors) & set(q.sectors):
            return False
        if q.stages and p.stage not in q.stages:
            return False
        countries = expand_geographies(q.geographies)
        return not (countries and p.country not in countries)

    def search(self, query: VendorQuery) -> list[VendorRecord]:
        recs = [_record(r, self.source) for r in self._rows]
        return [r for r in recs if self._matches(r, query)][: query.limit]

    def lookup(self, domain: str) -> VendorRecord | None:
        for r in self._rows:
            if (r.get("domain") or "").lower() == domain.lower():
                return _record(r, self.source)
        return None
