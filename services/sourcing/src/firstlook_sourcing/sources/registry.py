"""Company registries. Kenya's Business Registration Service (BRS) has no open
bulk API, so registry data arrives as extracts (CSV from the eCitizen search,
a data partner, or an official gazette). New incorporations are a discovery
signal; registration numbers become authoritative identifiers."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

from ..model import CompanyProfile, Observation
from ..taxonomy import sectors_in_text

_COLUMNS = {
    "name": ["company name", "name", "business name"],
    "number": ["registration number", "reg no", "company number", "registration no"],
    "date": ["registration date", "incorporation date", "date registered"],
    "kind": ["company type", "type"],
    "status": ["status"],
    "activity": ["nature of business", "principal activity", "business activity"],
}


def _col(headers: list[str], field: str) -> str | None:
    lookup = {h.strip().lower(): h for h in headers}
    return next((lookup[a] for a in _COLUMNS[field] if a in lookup), None)


def parse_registry_csv(
    text: str, registry: str = "ke-brs", country: str = "KE"
) -> list[tuple[CompanyProfile, Observation]]:
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    cols = {f: _col(headers, f) for f in _COLUMNS}
    out = []
    for row in reader:
        name = (row.get(cols["name"] or "") or "").strip()
        number = (row.get(cols["number"] or "") or "").strip()
        if not name or not number:
            continue
        status = (row.get(cols["status"] or "") or "").strip().lower()
        if status and status not in ("registered", "active", "live"):
            continue
        raw_date = (row.get(cols["date"] or "") or "").strip()
        try:
            registered = date.fromisoformat(raw_date) if raw_date else None
        except ValueError:
            registered = None
        activity = (row.get(cols["activity"] or "") or "").strip()
        profile = CompanyProfile(
            name=name.title() if name.isupper() else name,
            registry_id=f"{registry}:{number}",
            country=country,
            founded_year=registered.year if registered else None,
            sectors=sectors_in_text(activity),
            description=activity or None,
            source=f"registry:{registry}",
            source_ref=number,
        )
        when = datetime.combine(registered, datetime.min.time(), UTC) if registered else None
        out.append(
            (
                profile,
                Observation(
                    "incorporated",
                    1.0,
                    f"registry:{registry}",
                    observed_at=when,
                    detail={"number": number, "type": row.get(cols["kind"] or "")},
                ),
            )
        )
    return out
