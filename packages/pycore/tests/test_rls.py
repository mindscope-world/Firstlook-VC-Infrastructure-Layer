"""Tenant isolation is enforced by Postgres, not by application code."""

import os
import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from firstlook_core import audit
from firstlook_core.db import tenant_tx

pytestmark = pytest.mark.db


def _seed_rows(tenant_id, user_id):
    with tenant_tx(tenant_id) as conn:
        company = conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'company', 'Acme') RETURNING id",
            (tenant_id,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO companies (id, tenant_id, name, domain) VALUES (%s, %s, 'Acme', 'acme.io')",
            (company, tenant_id),
        )
        conn.execute(
            "INSERT INTO interactions (tenant_id, kind, external_id, occurred_at, body_text)"
            " VALUES (%s, 'email', %s, now(), 'secret deal terms')",
            (tenant_id, f"<{uuid.uuid4()}@x>"),
        )
        audit.record(conn, tenant_id, "test", "test")
    return company


def test_every_tenant_table_has_forced_rls(migrated_db):
    with psycopg.connect(os.environ["DATABASE_OWNER_URL"]) as conn:
        rows = conn.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
               AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id'
                           AND NOT a.attisdropped)
            """
        ).fetchall()
    assert rows, "no tenant tables found"
    missing = [name for name, enabled, forced in rows if not (enabled and forced)]
    assert missing == [], f"tables without forced RLS: {missing}"


def test_tenants_cannot_read_each_other(make_tenant):
    a, [(a_user, _)] = make_tenant("Fund A")
    b, [(b_user, _)] = make_tenant("Fund B")
    _seed_rows(a, a_user)
    _seed_rows(b, b_user)

    tables = [
        "users",
        "entities",
        "companies",
        "people",
        "identifiers",
        "interactions",
        "audit_events",
        "llm_budgets",
        "tenants",
    ]
    with tenant_tx(a) as conn:
        for table in tables:
            col = "id" if table == "tenants" else "tenant_id"
            ids = {r[col] for r in conn.execute(f"SELECT {col} FROM {table}").fetchall()}
            assert ids <= {a}, f"{table} leaked rows from another tenant"
            assert ids, f"{table} returned nothing for its own tenant"


def test_cannot_write_into_another_tenant(make_tenant):
    a, _ = make_tenant("Fund A")
    b, _ = make_tenant("Fund B")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), tenant_tx(a) as conn:
        conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'company', 'X')", (b,)
        )


def test_no_context_sees_nothing(make_tenant):
    a, [(a_user, _)] = make_tenant("Fund A")
    _seed_rows(a, a_user)
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        assert conn.execute("SELECT count(*) AS n FROM interactions").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM tenants").fetchone()["n"] == 0


def test_context_does_not_leak_between_transactions(make_tenant):
    a, [(a_user, _)] = make_tenant("Fund A")
    _seed_rows(a, a_user)
    with tenant_tx(a) as conn:
        assert conn.execute("SELECT count(*) AS n FROM interactions").fetchone()["n"] > 0
    # Same pool, new transaction, no context set -> RLS hides everything.
    from firstlook_core.db import _pool

    with _pool(os.environ["DATABASE_URL"]).connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM interactions").fetchone()["n"] == 0


def test_restricted_deals_visible_to_team_only(make_tenant):
    t, users = make_tenant(
        "Fund",
        [
            ("gp@f.vc", "GP", "partner"),
            ("assoc@f.vc", "Associate", "associate"),
            ("admin@f.vc", "Admin", "admin"),
        ],
    )
    (gp, _), (assoc, _), (admin, _) = users
    with tenant_tx(t) as conn:
        deal = conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name) VALUES (%s, 'deal', 'Secret')"
            " RETURNING id",
            (t,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO deals (id, tenant_id, name, restricted) VALUES (%s, %s, 'Secret', true)", (deal, t)
        )
        conn.execute(
            "INSERT INTO deal_team_members (tenant_id, deal_id, user_id) VALUES (%s, %s, %s)", (t, deal, gp)
        )
        conn.execute(
            "INSERT INTO interactions (tenant_id, kind, external_id, occurred_at, deal_id)"
            " VALUES (%s, 'email', 'deal-mail', now(), %s)",
            (t, deal),
        )

    def visible(user, role):
        with tenant_tx(t, user, role) as conn:
            deals = conn.execute("SELECT count(*) AS n FROM deals").fetchone()["n"]
            mails = conn.execute(
                "SELECT count(*) AS n FROM interactions WHERE external_id = 'deal-mail'"
            ).fetchone()["n"]
            return deals, mails

    assert visible(gp, "partner") == (1, 1)
    assert visible(assoc, "associate") == (0, 0)
    assert visible(admin, "admin") == (1, 1)


def test_private_interactions_visible_to_owner_only(make_tenant):
    t, users = make_tenant("Fund", [("a@f.vc", "A", "partner"), ("b@f.vc", "B", "partner")])
    (ua, _), (ub, _) = users
    with tenant_tx(t) as conn:
        conn.execute(
            "INSERT INTO interactions (tenant_id, kind, external_id, occurred_at, visibility, owner_user_id)"
            " VALUES (%s, 'email', 'private-1', now(), 'private', %s)",
            (t, ua),
        )
    with tenant_tx(t, ua, "partner") as conn:
        assert conn.execute("SELECT count(*) AS n FROM interactions").fetchone()["n"] == 1
    with tenant_tx(t, ub, "partner") as conn:
        assert conn.execute("SELECT count(*) AS n FROM interactions").fetchone()["n"] == 0


def test_connector_accounts_owned_by_user(make_tenant):
    t, users = make_tenant("Fund", [("a@f.vc", "A", "partner"), ("b@f.vc", "B", "partner")])
    (ua, _), (ub, _) = users
    with tenant_tx(t) as conn:
        conn.execute(
            "INSERT INTO connector_accounts (tenant_id, user_id, provider, account_email)"
            " VALUES (%s, %s, 'google', 'a@f.vc')",
            (t, ua),
        )
    with tenant_tx(t, ub, "partner") as conn:
        assert conn.execute("SELECT count(*) AS n FROM connector_accounts").fetchone()["n"] == 0
    with tenant_tx(t, ua, "partner") as conn:
        assert conn.execute("SELECT count(*) AS n FROM connector_accounts").fetchone()["n"] == 1


def test_audit_events_are_append_only(make_tenant):
    t, _ = make_tenant("Fund")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), tenant_tx(t) as conn:
        conn.execute("UPDATE audit_events SET action = 'tampered'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), tenant_tx(t) as conn:
        conn.execute("DELETE FROM audit_events")
    # Even the owner role is stopped by the trigger.
    with (
        psycopg.connect(os.environ["DATABASE_OWNER_URL"]) as conn,
        pytest.raises(psycopg.errors.RaiseException),
    ):
        conn.execute("DELETE FROM audit_events")
