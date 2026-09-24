"""Write CRM records into the graph through entity resolution.

CRM IDs are stored as `crm_id` identifiers ("hubspot:123"), so re-running an
import updates the same entities instead of duplicating them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import psycopg

from firstlook_core import audit, outbox
from firstlook_core.llm import LlmClient
from firstlook_resolver.er import Resolver

from .model import CrmRecords

STAGE_MAP = {
    # Common pipeline names across CRMs -> Firstlook stages.
    "lead": "sourced",
    "sourced": "sourced",
    "new": "sourced",
    "inbound": "sourced",
    "prospect": "sourced",
    "first meeting": "screening",
    "screening": "screening",
    "qualified": "screening",
    "intro call": "screening",
    "diligence": "diligence",
    "due diligence": "diligence",
    "dd": "diligence",
    "deep dive": "diligence",
    "ic": "ic",
    "investment committee": "ic",
    "partner meeting": "ic",
    "term sheet": "term_sheet",
    "negotiation": "term_sheet",
    "closing": "term_sheet",
    "closed won": "invested",
    "won": "invested",
    "invested": "invested",
    "portfolio": "invested",
    "closed lost": "passed",
    "lost": "passed",
    "passed": "passed",
    "pass": "passed",
    "declined": "passed",
}


def map_stage(stage: str | None) -> str:
    if not stage:
        return "sourced"
    return STAGE_MAP.get(stage.strip().lower().replace("_", " "), "sourced")


@dataclass
class ImportResult:
    companies: int = 0
    people: int = 0
    deals: int = 0
    notes: int = 0
    queued_for_review: int = 0
    errors: list[str] = field(default_factory=list)


def import_records(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    vendor: str,
    records: CrmRecords,
    *,
    source_id: UUID | None = None,
    actor_id: UUID | None = None,
    llm: LlmClient | None = None,
) -> ImportResult:
    tenant_id = str(tenant_id)
    resolver = Resolver(conn, tenant_id, llm)
    result = ImportResult()
    company_ids: dict[str, UUID] = {}

    def company(name: str | None, domain: str | None) -> UUID | None:
        key = (domain or name or "").lower()
        if not key:
            return None
        if key not in company_ids:
            res = resolver.resolve_company(name=name, domain=domain, source_id=source_id)
            if res is None:
                return None
            company_ids[key] = res.entity_id
            result.queued_for_review += int(res.queued)
        return company_ids[key]

    for c in records.companies:
        entity = None
        if c.crm_id:
            entity = resolver._by_identifier("crm_id", c.crm_id)
        if entity is None:
            res = resolver.resolve_company(
                name=c.name,
                domain=c.domain,
                source_id=source_id,
                country=c.country,
                description=c.description,
            )
            if res is None:
                continue
            entity = res.entity_id
            result.queued_for_review += int(res.queued)
            if c.crm_id:
                resolver.add_identifier(entity, "crm_id", c.crm_id, source_id)
        conn.execute(
            "UPDATE companies SET country = coalesce(country, %s), description = coalesce(description, %s)"
            " WHERE id = %s",
            (c.country, c.description, entity),
        )
        company_ids[(c.domain or c.name).lower()] = entity
        result.companies += 1

    for p in records.people:
        cid = company(p.company_name, p.company_domain)
        res = resolver.resolve_person(
            email=p.email,
            name=p.name,
            title=p.title,
            company_id=cid,
            source_id=source_id,
            crm_id=p.crm_id,
            context=f"{vendor} import",
        )
        if res is None:
            continue
        if p.linkedin:
            resolver.add_identifier(res.entity_id, "linkedin", p.linkedin, source_id)
        result.people += 1
        result.queued_for_review += int(res.queued)

    for d in records.deals:
        cid = company(d.company_name, d.company_domain)
        existing = resolver._by_identifier("crm_id", d.crm_id) if d.crm_id else None
        stage = map_stage(d.stage)
        if existing:
            conn.execute(
                "UPDATE deals SET stage = %s, round_size_usd = coalesce(%s, round_size_usd),"
                " updated_at = now() WHERE id = %s",
                (stage, d.amount_usd, existing),
            )
        else:
            deal_id = conn.execute(
                "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'deal', %s) RETURNING id",
                (tenant_id, d.name),
            ).fetchone()["id"]
            conn.execute(
                "INSERT INTO deals (id, tenant_id, company_id, name, stage, round_size_usd, created_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (deal_id, tenant_id, cid, d.name, stage, d.amount_usd, actor_id),
            )
            if d.crm_id:
                resolver.add_identifier(deal_id, "crm_id", d.crm_id, source_id)
        result.deals += 1

    for n in records.notes:
        external_id = n.crm_id or "note:" + hashlib.sha256(n.body.encode()).hexdigest()[:32]
        row = conn.execute(
            "INSERT INTO interactions (tenant_id, source_id, kind, external_id, subject, occurred_at, body_text,"
            " body_full_text, direction, owner_user_id) VALUES (%s, %s, 'note', %s, %s, %s, %s, %s, 'internal', %s)"
            " ON CONFLICT (tenant_id, kind, external_id) DO NOTHING RETURNING id",
            (
                tenant_id,
                source_id,
                external_id,
                n.title or f"{vendor} note",
                n.occurred_at or datetime.now(UTC),
                n.body,
                n.body,
                actor_id,
            ),
        ).fetchone()
        if row is None:
            continue
        for email in n.person_emails:
            res = resolver.resolve_person(email=email, source_id=source_id)
            if res:
                conn.execute(
                    "INSERT INTO interaction_participants (tenant_id, interaction_id, person_id, email, role)"
                    " VALUES (%s, %s, %s, %s, 'mentioned')",
                    (tenant_id, row["id"], res.entity_id, email),
                )
        outbox.enqueue(
            conn,
            tenant_id,
            outbox.Topics.INTERACTION_RESOLVED,
            {"interaction_id": str(row["id"]), "kind": "note"},
            key=str(row["id"]),
        )
        result.notes += 1

    audit.record(
        conn,
        tenant_id,
        "crm.import",
        "import",
        source_id,
        actor_type="user" if actor_id else "service",
        actor_id=actor_id,
        details={"vendor": vendor, **result.__dict__},
    )
    return result
