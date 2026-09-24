from datetime import UTC, datetime, timedelta

import pytest

from firstlook_resolver.er import (
    Resolver,
    domain_of,
    is_business_domain,
    name_from_email,
    normalise_company_name,
    normalise_person_name,
    person_name_similarity,
)
from firstlook_resolver.strength import PairStats, score


def test_name_helpers():
    assert normalise_person_name("Dr. Doe, Jane") == "jane doe"
    assert normalise_company_name("Acme Technologies Ltd.") == "acme"
    assert name_from_email("jane.doe+vc@acme.io") == "Jane Doe"
    assert domain_of("A@Acme.IO") == "acme.io"
    assert not is_business_domain("gmail.com") and is_business_domain("acme.io")
    assert person_name_similarity("W. Kamau", "Wanjiru Kamau") >= 0.9
    assert person_name_similarity("Peter Kamau", "Wanjiru Kamau") < 0.7


def test_strength_components():
    now = datetime(2026, 9, 25, tzinfo=UTC)
    fresh = score(
        PairStats(last_at=now - timedelta(days=1), weighted=10, total=10, outbound=5, inbound=5), now
    )
    stale = score(
        PairStats(last_at=now - timedelta(days=180), weighted=10, total=10, outbound=5, inbound=5), now
    )
    one_way = score(
        PairStats(last_at=now - timedelta(days=1), weighted=10, total=10, outbound=10, inbound=0), now
    )
    assert fresh["strength"] > stale["strength"]
    assert fresh["strength"] > one_way["strength"]
    assert one_way["reciprocity"] == 0
    assert stale["recency"] == pytest.approx(0.5**4, rel=1e-3)
    assert 0 <= fresh["strength"] <= 1


@pytest.mark.db
def test_resolver_rules(make_tenant, llm):
    from firstlook_core.db import tenant_tx

    t, _ = make_tenant("ER Fund")
    with tenant_tx(t) as conn:
        r = Resolver(conn, t, llm)
        a = r.resolve_person(email="Jane@Acme.io", name="Jane Doe")
        assert a.created and a.method == "new"
        # Deterministic: same email (case-insensitive).
        assert r.resolve_person(email="jane@acme.io", name="J Doe").entity_id == a.entity_id
        # Same domain, near-identical name -> auto link, new email becomes an identifier.
        b = r.resolve_person(email="jane.doe@acme.io", name="Jane A. Doe")
        assert b.entity_id == a.entity_id and b.method == "similarity"
        # Personal address, similar name -> provisional + review queue.
        c = r.resolve_person(email="jdoe@gmail.com", name="J. Doe")
        assert c.queued and c.entity_id != a.entity_id
        # Different person, different org -> new, not queued.
        d = r.resolve_person(email="peter@other.io", name="Peter Kamau")
        assert d.method == "new" and not d.queued
        # Company by domain created once and linked.
        acme = r.resolve_company(domain="acme.io")
        assert acme.method == "identifier"
        row = conn.execute("SELECT company_id FROM people WHERE id = %s", (a.entity_id,)).fetchone()
        assert row["company_id"] == acme.entity_id
        # Free-mail domains never become companies.
        assert r.resolve_company(domain="gmail.com") is None
        # Registry ID is authoritative.
        k = r.resolve_company(name="Kilimo Data Ltd", registry_id="PVT-123")
        assert r.resolve_company(name="Kilimo", registry_id="PVT-123").entity_id == k.entity_id
