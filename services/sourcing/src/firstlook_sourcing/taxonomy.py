"""Shared vocabulary for theses and company profiles: sectors, stages, regions.

Sources describe the same thing many ways ("Fin-Tech", "Payments", "Series A",
"A round", "Kenya", "KE"). Everything is normalised here before it is stored
or compared.
"""

from __future__ import annotations

import re

from firstlook_core.geo import COUNTRIES, normalise_country  # noqa: F401 - re-exported

SECTORS: dict[str, list[str]] = {
    "fintech": [
        "fintech",
        "fin-tech",
        "payments",
        "lending",
        "credit",
        "banking",
        "neobank",
        "remittance",
        "mobile money",
        "wealth",
        "savings",
        "financial services",
    ],
    "insurtech": ["insurtech", "insurance"],
    "agritech": [
        "agritech",
        "agtech",
        "agriculture",
        "agricultural",
        "farming",
        "farm",
        "farmers",
        "agri",
        "food supply",
        "smallholder",
        "dairy",
        "grain",
    ],
    "healthtech": ["healthtech", "health", "healthcare", "medtech", "pharmacy", "telemedicine", "clinic"],
    "edtech": ["edtech", "education", "learning", "schools"],
    "logistics": ["logistics", "freight", "delivery", "supply chain", "trucking", "last mile"],
    "commerce": [
        "commerce",
        "e-commerce",
        "ecommerce",
        "retail",
        "b2b commerce",
        "marketplace",
        "informal retail",
    ],
    "climate": [
        "climate",
        "energy",
        "solar",
        "clean energy",
        "cleantech",
        "off-grid",
        "e-mobility",
        "carbon",
    ],
    "mobility": ["mobility", "transport", "ride-hailing", "motorcycle", "boda"],
    "proptech": ["proptech", "real estate", "housing", "construction"],
    "saas": ["saas", "b2b software", "enterprise software", "hr tech", "productivity"],
    "devtools": ["devtools", "developer tools", "infrastructure", "api", "cloud"],
    "ai": ["ai", "artificial intelligence", "machine learning", "ml"],
    "media": ["media", "creator", "entertainment", "content"],
}

STAGES = ["pre-seed", "seed", "series-a", "series-b", "series-c", "growth"]
_STAGE_ALIASES = {
    "preseed": "pre-seed",
    "pre seed": "pre-seed",
    "angel": "pre-seed",
    "friends and family": "pre-seed",
    "seed": "seed",
    "seed extension": "seed",
    "seed+": "seed",
    "bridge": "seed",
    "series a": "series-a",
    "a": "series-a",
    "series-a": "series-a",
    "series b": "series-b",
    "b": "series-b",
    "series-b": "series-b",
    "series c": "series-c",
    "c": "series-c",
    "series-c": "series-c",
    "series d": "growth",
    "growth": "growth",
    "late stage": "growth",
    "pre-ipo": "growth",
}

REGIONS: dict[str, list[str]] = {
    "east-africa": ["KE", "UG", "TZ", "RW", "ET", "BI", "SS", "SO", "DJ", "ER"],
    "west-africa": ["NG", "GH", "SN", "CI", "BJ", "TG", "BF", "ML", "NE", "SL", "LR", "GM", "GN", "CV"],
    "southern-africa": ["ZA", "ZW", "ZM", "BW", "NA", "MZ", "MW", "LS", "SZ", "AO", "MG", "MU"],
    "north-africa": ["EG", "MA", "TN", "DZ", "LY", "SD"],
    "central-africa": ["CD", "CM", "CG", "GA", "CF", "TD", "GQ"],
}
REGIONS["africa"] = sorted({c for cs in REGIONS.values() for c in cs})


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_/|]+", " ", s.strip().lower()))


def normalise_sector(value: str) -> str | None:
    v = _clean(value)
    if v in SECTORS:
        return v
    for key, aliases in SECTORS.items():
        if v in aliases or any(re.search(rf"\b{re.escape(a)}\b", v) for a in aliases):
            return key
    return None


def normalise_sectors(values: list[str] | str | None) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = re.split(r"[,;]", values)
    out: list[str] = []
    for v in values:
        s = normalise_sector(v)
        if s and s not in out:
            out.append(s)
    return out


def sectors_in_text(text: str | None) -> list[str]:
    """Every sector mentioned in free text (registry activities, descriptions)."""
    if not text:
        return []
    t = _clean(text)
    return [
        key
        for key, aliases in SECTORS.items()
        if any(re.search(rf"\b{re.escape(a)}\b", t) for a in [key, *aliases])
    ]


def normalise_stage(value: str | None) -> str | None:
    if not value:
        return None
    v = _clean(value).replace("round", "").strip()
    if v in STAGES:
        return v
    return _STAGE_ALIASES.get(v)


def stage_distance(a: str | None, b: str | None) -> int | None:
    if a not in STAGES or b not in STAGES:
        return None
    return abs(STAGES.index(a) - STAGES.index(b))


def expand_geographies(geos: list[str]) -> set[str]:
    """Thesis geographies (regions or countries) -> set of ISO country codes."""
    out: set[str] = set()
    for g in geos:
        key = _clean(g).replace(" ", "-")
        if key in REGIONS:
            out |= set(REGIONS[key])
        elif (c := normalise_country(g)) is not None:
            out.add(c)
    return out
