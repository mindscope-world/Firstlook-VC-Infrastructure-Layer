from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

VENDORS = ("affinity", "hubspot", "salesforce", "airtable")


@dataclass
class CrmCompany:
    name: str
    domain: str | None = None
    crm_id: str | None = None
    country: str | None = None
    description: str | None = None


@dataclass
class CrmPerson:
    name: str
    email: str | None = None
    title: str | None = None
    company_name: str | None = None
    company_domain: str | None = None
    crm_id: str | None = None
    phone: str | None = None
    linkedin: str | None = None


@dataclass
class CrmDeal:
    name: str
    stage: str | None = None
    amount_usd: float | None = None
    company_name: str | None = None
    company_domain: str | None = None
    crm_id: str | None = None


@dataclass
class CrmNote:
    body: str
    occurred_at: datetime | None = None
    person_emails: list[str] = field(default_factory=list)
    company_name: str | None = None
    crm_id: str | None = None
    title: str | None = None


@dataclass
class CrmRecords:
    companies: list[CrmCompany] = field(default_factory=list)
    people: list[CrmPerson] = field(default_factory=list)
    deals: list[CrmDeal] = field(default_factory=list)
    notes: list[CrmNote] = field(default_factory=list)

    def extend(self, other: CrmRecords) -> None:
        self.companies += other.companies
        self.people += other.people
        self.deals += other.deals
        self.notes += other.notes

    @property
    def total(self) -> int:
        return len(self.companies) + len(self.people) + len(self.deals) + len(self.notes)
