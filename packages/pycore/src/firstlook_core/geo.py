"""Country names to ISO 3166-1 alpha-2 codes. Companies store the code."""

from __future__ import annotations

import re

COUNTRIES = {
    "kenya": "KE",
    "uganda": "UG",
    "tanzania": "TZ",
    "rwanda": "RW",
    "ethiopia": "ET",
    "nigeria": "NG",
    "ghana": "GH",
    "senegal": "SN",
    "cote d'ivoire": "CI",
    "ivory coast": "CI",
    "south africa": "ZA",
    "egypt": "EG",
    "morocco": "MA",
    "tunisia": "TN",
    "zambia": "ZM",
    "zimbabwe": "ZW",
    "botswana": "BW",
    "cameroon": "CM",
    "drc": "CD",
    "democratic republic of the congo": "CD",
    "mozambique": "MZ",
    "malawi": "MW",
    "benin": "BJ",
    "togo": "TG",
    "burundi": "BI",
    "somalia": "SO",
    "south sudan": "SS",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "india": "IN",
}


def normalise_country(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if len(v) == 2 and v.isalpha():
        return v.upper()
    return COUNTRIES.get(re.sub(r"\s+", " ", v.lower()))
