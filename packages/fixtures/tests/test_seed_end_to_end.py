"""End to end over the synthetic fund: raw email -> outbox -> bus -> resolver ->
graph -> extraction, exactly the production event flow, in-process."""

import pytest

from firstlook_core.adapters.bus import InMemoryBus
from firstlook_core.db import system_tx, tenant_tx
from firstlook_core.llm import set_llm
from firstlook_fixtures.fund import harbor, savanna
from firstlook_fixtures.seed import golden_llm, seed_fund

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def seeded(migrated_db):
    with system_tx() as conn:
        for row in conn.execute("SELECT id FROM tenants WHERE slug IN ('savanna', 'harbor')").fetchall():
            conn.execute("SELECT purge_tenant(%s)", (row["id"],))
    fixtures = [savanna(), harbor()]
    set_llm(golden_llm(fixtures))
    bus = InMemoryBus()
    ids = {f.slug: seed_fund(f, bus) for f in fixtures}
    yield ids, bus
    set_llm(None)


def q(tenant_id, sql, *params, user=None, role="service"):
    with tenant_tx(tenant_id, user, role) as conn:
        return conn.execute(sql, params).fetchall()


def test_emails_become_interactions_and_bulk_mail_is_skipped(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    subjects = {r["subject"] for r in q(t, "SELECT subject FROM interactions WHERE kind = 'email'")}
    assert "Intro: Paul (Savanna) <> Wanjiru (Kilimo Data)" in subjects
    assert "This week in African tech" not in subjects  # List-Unsubscribe -> automated
    # Internal-only meeting is skipped; external ones are kept.
    meetings = {r["subject"] for r in q(t, "SELECT subject FROM interactions WHERE kind = 'meeting'")}
    assert meetings == {"Savanna <> Kilimo Data", "PesaFlow diligence session"}
    assert q(t, "SELECT count(*) AS n FROM interactions WHERE kind = 'transcript'")[0]["n"] == 1


def test_quotes_and_signatures_are_stripped(seeded):
    ids, _ = seeded
    row = q(
        ids["savanna"],
        "SELECT body_text, signature FROM interactions WHERE external_id = %s",
        "<kilimo-deck@fixtures.firstlook.local>",
    )[0]
    assert "On Mon, Joseph Mutua" not in row["body_text"]
    assert row["body_text"].endswith("Would you have 30 minutes next week?")
    assert row["signature"].startswith("Best regards,")


def test_signature_enriches_title_and_attachment_stored(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    person = q(t, "SELECT title FROM people WHERE primary_email = 'wanjiru@kilimodata.co.ke'")[0]
    assert person["title"] == "Co-founder & CEO"
    att = q(t, "SELECT filename, object_uri FROM attachments")
    assert [a["filename"] for a in att] == ["Kilimo Data - Seed Deck.pdf"]
    assert att[0]["object_uri"].startswith("file://tenants/")


def test_entity_resolution_auto_links_same_domain_variant(seeded):
    ids, _ = seeded
    rows = q(
        ids["savanna"],
        "SELECT i.value::text AS email, coalesce(e.merged_into, e.id) AS person FROM identifiers i"
        " JOIN entities e ON e.id = i.entity_id WHERE i.value IN ('jane@pesaflow.africa','jane.achieng@pesaflow.africa')",
    )
    assert len(rows) == 2
    assert rows[0]["person"] == rows[1]["person"], "Jane's two addresses should resolve to one person"


def test_entity_resolution_queues_personal_address_for_review(seeded):
    ids, _ = seeded
    pending = q(
        ids["savanna"],
        "SELECT c.mention, e.canonical_name FROM er_candidates c JOIN entities e ON e.id = c.candidate_entity_id"
        " WHERE c.status = 'pending'",
    )
    mentions = {(p["mention"].get("email"), p["canonical_name"]) for p in pending}
    assert ("wanjiru.kamau@gmail.com", "Wanjiru Kamau") in mentions


def test_review_merge_folds_provisional_person(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    cand = q(
        t,
        "SELECT id, provisional_entity_id, candidate_entity_id FROM er_candidates"
        " WHERE mention->>'email' = 'wanjiru.kamau@gmail.com'",
    )[0]
    user = q(t, "SELECT id FROM users WHERE email = 'grace@savanna.vc'")[0]["id"]
    with tenant_tx(t, user, "associate") as conn:
        conn.execute("SELECT er_decide(%s, 'merged', %s)", (cand["id"], user))
    ident = q(t, "SELECT entity_id FROM identifiers WHERE value = 'wanjiru.kamau@gmail.com'")[0]
    assert ident["entity_id"] == cand["candidate_entity_id"]
    merged = q(t, "SELECT merged_into FROM entities WHERE id = %s", cand["provisional_entity_id"])[0]
    assert merged["merged_into"] == cand["candidate_entity_id"]
    parts = q(t, "SELECT person_id FROM interaction_participants WHERE email = 'wanjiru.kamau@gmail.com'")
    assert parts and all(p["person_id"] == cand["candidate_entity_id"] for p in parts)
    audit = q(t, "SELECT action FROM audit_events WHERE resource_id = %s", str(cand["id"]))
    assert [a["action"] for a in audit] == ["er.merged"]


def test_extractions_have_verbatim_citations(seeded):
    ids, _ = seeded
    rows = q(
        ids["savanna"],
        "SELECT x.kind, x.citations, i.body_text FROM extractions x JOIN interactions i ON i.id = x.interaction_id",
    )
    kinds = {r["kind"] for r in rows}
    assert kinds == {"intro", "next_step", "deal_mention"}
    for r in rows:
        c = r["citations"][0]
        assert r["body_text"][c["start"] : c["end"]] == c["quote"]


def test_prompt_injection_text_does_not_act(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    # The Duka Direct email asks AI assistants to mark the deal invested. Nothing
    # but a proposed deal mention results; no deal exists until a user accepts.
    assert q(t, "SELECT count(*) AS n FROM deals WHERE name = 'Duka Direct'")[0]["n"] == 0
    assert (
        q(t, "SELECT status FROM extractions WHERE payload->>'company_name' = 'Duka Direct'")[0]["status"]
        == "proposed"
    )


def test_accepting_deal_mention_creates_deal_and_event(seeded):
    ids, bus = seeded
    t = ids["savanna"]
    x = q(t, "SELECT id FROM extractions WHERE payload->>'company_name' = 'Duka Direct'")[0]
    user = q(t, "SELECT id FROM users WHERE email = 'grace@savanna.vc'")[0]["id"]
    with tenant_tx(t, user, "associate") as conn:
        deal_id = conn.execute(
            "SELECT decide_extraction(%s, 'accepted', %s) AS d", (x["id"], user)
        ).fetchone()["d"]
    deal = q(
        t,
        "SELECT d.stage, c.domain::text AS domain FROM deals d JOIN companies c ON c.id = d.company_id"
        " WHERE d.id = %s",
        deal_id,
    )[0]
    assert deal == {"stage": "sourced", "domain": "dukadirect.com"}
    events = q(t, "SELECT payload FROM outbox WHERE topic = 'deals.events'")
    assert any(e["payload"]["deal_id"] == str(deal_id) for e in events)


def test_accepting_intro_adds_edges_and_warm_path(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    x = q(
        t,
        "SELECT id FROM extractions WHERE kind = 'intro' AND payload->'introducer'->>'email' = 'joseph@riftvalley.vc'"
        " AND payload->>'status' = 'made' AND payload->'introduced'->0->>'email' = 'kofi@solarnest.io'",
    )[0]
    user = q(t, "SELECT id FROM users WHERE email = 'amani@savanna.vc'")[0]["id"]
    with tenant_tx(t, user, "partner") as conn:
        conn.execute("SELECT decide_extraction(%s, 'accepted', %s)", (x["id"], user))
    kofi = q(t, "SELECT id FROM people WHERE primary_email = 'kofi@solarnest.io'")[0]["id"]
    assert (
        q(
            t,
            "SELECT count(*) AS n FROM edges WHERE type = 'introduced' AND (src_id = %s OR dst_id = %s)",
            kofi,
            kofi,
        )[0]["n"]
        >= 1
    )

    solarnest = q(t, "SELECT id FROM companies WHERE domain = 'solarnest.io'")[0]["id"]
    paths = q(t, "SELECT path, score, hops FROM warm_paths(%s)", solarnest)
    assert paths, "expected at least one warm path to SolarNest"
    assert all(p["path"][-1] == kofi for p in paths)
    assert paths == sorted(paths, key=lambda p: -p["score"])


def test_relationship_strength_reflects_recency_and_reciprocity(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    rows = q(
        t,
        """SELECT pi.primary_email::text AS us, px.primary_email::text AS them, e.props
                   FROM edges e JOIN people pi ON pi.id = e.src_id JOIN people px ON px.id = e.dst_id
                   WHERE e.type = 'knows' AND e.valid_to IS NULL""",
    )
    by_pair = {(r["us"], r["them"]): r["props"] for r in rows}
    wanjiru = by_pair[("paul@savanna.vc", "wanjiru@kilimodata.co.ke")]
    joseph = by_pair[("paul@savanna.vc", "joseph@riftvalley.vc")]
    # Joseph's only direct thread with Paul is months old, so recency has decayed.
    assert joseph["recency"] < wanjiru["recency"]
    assert wanjiru["reciprocity"] > 0 and wanjiru["inbound"] >= 1 and wanjiru["outbound"] >= 1
    assert 0 < wanjiru["strength"] <= 1
    nia = by_pair[("tom@savanna.vc", "nia@afyalink.health")]
    assert nia["reciprocity"] == 1.0


def test_crm_import_links_to_existing_entities(seeded):
    ids, _ = seeded
    t = ids["savanna"]
    kilimo = q(
        t,
        "SELECT c.country, count(*) OVER () AS n FROM companies c JOIN entities e ON e.id = c.id"
        " WHERE c.domain = 'kilimodata.co.ke' AND e.merged_into IS NULL",
    )
    assert len(kilimo) == 1 and kilimo[0]["country"] == "KE"
    deals = {r["name"]: r["stage"] for r in q(t, "SELECT name, stage FROM deals")}
    assert deals["AfyaLink Seed"] == "invested"
    assert deals["Safiri Logistics Pre-seed"] == "diligence"
    nia = q(t, "SELECT title FROM people WHERE primary_email = 'nia@afyalink.health'")[0]
    assert nia["title"] == "Co-founder & CEO"


def test_tenants_are_isolated(seeded):
    ids, _ = seeded
    savanna_bodies = " ".join(
        r["body_text"] or "" for r in q(ids["savanna"], "SELECT body_text FROM interactions")
    )
    assert "pre-money is $9M" not in savanna_bodies
    # Same founder email exists in both tenants as separate entities.
    a = q(ids["savanna"], "SELECT entity_id FROM identifiers WHERE value = 'wanjiru@kilimodata.co.ke'")[0]
    b = q(ids["harbor"], "SELECT entity_id FROM identifiers WHERE value = 'wanjiru@kilimodata.co.ke'")[0]
    assert a["entity_id"] != b["entity_id"]
