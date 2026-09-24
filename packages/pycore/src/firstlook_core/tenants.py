"""Tenant provisioning."""

from __future__ import annotations

from uuid import UUID, uuid4

import psycopg

from . import audit
from .crypto import new_wrapped_dek
from .db import set_context


def create_tenant(conn: psycopg.Connection, name: str, slug: str, workos_org_id: str | None = None) -> UUID:
    """Create a tenant with its own wrapped data key and default LLM budget.

    Runs on any connection: it sets the new tenant's context itself so the
    inserts pass the RLS WITH CHECK clauses.
    """
    tenant_id = uuid4()
    set_context(conn, tenant_id, None, "service")
    wrapped, key_ref = new_wrapped_dek(tenant_id)
    conn.execute(
        "INSERT INTO tenants (id, name, slug, workos_org_id, wrapped_dek, kms_key_ref) VALUES (%s, %s, %s, %s, %s, %s)",
        (str(tenant_id), name, slug, workos_org_id, wrapped, key_ref),
    )
    conn.execute("INSERT INTO llm_budgets (tenant_id) VALUES (%s)", (str(tenant_id),))
    audit.record(conn, tenant_id, "tenant.created", "tenant", tenant_id, actor_type="system")
    return tenant_id


def create_user(
    conn: psycopg.Connection, tenant_id: UUID, email: str, name: str, role: str = "associate"
) -> tuple[UUID, UUID]:
    """Create a user and their internal person node. Returns (user_id, person_id)."""
    person_id = conn.execute(
        "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'person', %s) RETURNING id",
        (str(tenant_id), name),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO people (id, tenant_id, full_name, primary_email, is_internal) VALUES (%s, %s, %s, %s, true)",
        (person_id, str(tenant_id), name, email),
    )
    conn.execute(
        "INSERT INTO identifiers (tenant_id, entity_id, kind, value) VALUES (%s, %s, 'email', %s)",
        (str(tenant_id), person_id, email.lower()),
    )
    user_id = conn.execute(
        "INSERT INTO users (tenant_id, email, name, role, person_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (str(tenant_id), email, name, role, person_id),
    ).fetchone()["id"]
    return user_id, person_id
