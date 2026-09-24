"""CSV exports from Affinity, HubSpot, Salesforce and Airtable.

Headers differ by vendor and by how each firm customised its CRM, so columns
are matched through alias lists (case/space/punctuation-insensitive). A
caller can pass an explicit mapping {csv column: field} for unusual exports.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

from .model import CrmCompany, CrmDeal, CrmNote, CrmPerson, CrmRecords

ALIASES: dict[str, list[str]] = {
    "id": [
        "record id",
        "id",
        "organization id",
        "person id",
        "opportunity id",
        "entity id",
        "record_id",
        "list entry id",
        "airtable id",
    ],
    "first_name": ["first name", "firstname", "first"],
    "last_name": ["last name", "lastname", "last"],
    "full_name": ["name", "full name", "contact name", "person", "person name"],
    "email": ["email", "primary email", "email address", "e-mail", "work email", "emails"],
    "title": ["job title", "title", "role", "position"],
    "company_name": [
        "company name",
        "company",
        "organization",
        "organizations",
        "account name",
        "account.name",
        "associated company",
        "organization name",
        "companies",
    ],
    "company_domain": [
        "company domain name",
        "domain",
        "website",
        "company website",
        "website url",
        "account.website",
        "organization domain",
        "url",
    ],
    "phone": ["phone", "phone number", "mobile", "mobile phone number"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "country": ["country", "country/region", "billingcountry", "billing country", "location", "hq country"],
    "description": ["description", "about", "company description", "one liner", "summary"],
    "deal_name": ["deal name", "dealname", "opportunity name", "opportunity", "deal"],
    "stage": ["deal stage", "stage", "stagename", "status", "pipeline stage"],
    "amount": ["amount", "deal amount", "round size", "amount (usd)", "investment amount"],
    "note": ["note", "notes", "body", "content", "note body", "comments"],
    "date": ["date", "created at", "created date", "createddate", "note date", "activity date", "timestamp"],
}


def _key(header: str) -> str:
    return re.sub(r"[^a-z0-9./]+", " ", header.lower()).strip()


def _resolve_columns(headers: list[str], mapping: dict[str, str] | None) -> dict[str, str]:
    columns: dict[str, str] = {}
    if mapping:
        columns.update({field: col for col, field in mapping.items() if col in headers})
    lookup = {_key(h): h for h in headers}
    for field, aliases in ALIASES.items():
        if field in columns:
            continue
        for alias in aliases:
            if alias in lookup:
                columns[field] = lookup[alias]
                break
    return columns


def detect_object(columns: dict[str, str]) -> str:
    if "note" in columns:
        return "notes"
    if "deal_name" in columns or ("stage" in columns and "email" not in columns):
        return "deals"
    if "email" in columns or "first_name" in columns:
        return "people"
    return "companies"


def clean_domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.removeprefix("www.").split("/")[0].split("?")[0]
    return value if "." in value else None


def _amount(value: str | None) -> float | None:
    if not value:
        return None
    m = re.sub(r"[^\d.]", "", value.replace(",", ""))
    try:
        amount = float(m)
    except ValueError:
        return None
    lowered = value.lower()
    if lowered.rstrip().endswith("m"):
        amount *= 1_000_000
    elif lowered.rstrip().endswith("k"):
        amount *= 1_000
    return amount


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M",
    ):
        try:
            return datetime.strptime(value.strip().replace("Z", "+0000"), fmt)
        except ValueError:
            continue
    return None


def parse_csv(
    data: bytes | str, vendor: str, object_type: str | None = None, mapping: dict[str, str] | None = None
) -> CrmRecords:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    columns = _resolve_columns(headers, mapping)
    object_type = object_type or detect_object(columns)
    records = CrmRecords()

    def get(row: dict[str, Any], field: str) -> str | None:
        col = columns.get(field)
        value = (row.get(col) or "").strip() if col else ""
        return value or None

    for row in reader:
        rid = get(row, "id")
        crm_id = f"{vendor}:{rid}" if rid else None
        if object_type == "people":
            name = get(row, "full_name") or " ".join(
                x for x in (get(row, "first_name"), get(row, "last_name")) if x
            )
            emails = [e.strip() for e in re.split(r"[;,\s]+", get(row, "email") or "") if "@" in e]
            if not name and not emails:
                continue
            records.people.append(
                CrmPerson(
                    name=name or emails[0],
                    email=emails[0] if emails else None,
                    title=get(row, "title"),
                    company_name=(get(row, "company_name") or "").split(";")[0].strip() or None,
                    company_domain=clean_domain(get(row, "company_domain")),
                    crm_id=crm_id,
                    phone=get(row, "phone"),
                    linkedin=get(row, "linkedin"),
                )
            )
        elif object_type == "companies":
            name = get(row, "full_name") or get(row, "company_name")
            if not name:
                continue
            records.companies.append(
                CrmCompany(
                    name=name,
                    domain=clean_domain(get(row, "company_domain")),
                    crm_id=crm_id,
                    country=get(row, "country"),
                    description=get(row, "description"),
                )
            )
        elif object_type == "deals":
            name = get(row, "deal_name") or get(row, "full_name") or get(row, "company_name")
            if not name:
                continue
            records.deals.append(
                CrmDeal(
                    name=name,
                    stage=get(row, "stage"),
                    amount_usd=_amount(get(row, "amount")),
                    company_name=get(row, "company_name") or name,
                    company_domain=clean_domain(get(row, "company_domain")),
                    crm_id=crm_id,
                )
            )
        elif object_type == "notes":
            body = get(row, "note")
            if not body:
                continue
            emails = [e for e in re.split(r"[;,\s]+", get(row, "email") or "") if "@" in e]
            records.notes.append(
                CrmNote(
                    body=body,
                    occurred_at=_date(get(row, "date")),
                    person_emails=emails,
                    company_name=get(row, "company_name"),
                    crm_id=crm_id,
                    title=get(row, "full_name"),
                )
            )
        else:
            raise ValueError(f"unknown object type {object_type!r}")
    return records
