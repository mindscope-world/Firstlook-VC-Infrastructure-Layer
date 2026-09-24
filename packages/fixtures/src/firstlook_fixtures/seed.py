"""Seed the local stack with the synthetic funds.

    make seed                      # golden extractions, no model calls
    make seed ARGS="--llm gateway" # real extractions through the LLM gateway

Runs the same event flow as production, in-process: raw items land in
object storage with outbox rows, the outbox relays to an in-memory bus, and
the resolver and AI consumers handle the events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any
from uuid import UUID

from firstlook_core import outbox
from firstlook_core.adapters.bus import InMemoryBus
from firstlook_core.db import system_tx, tenant_tx
from firstlook_core.llm import FakeLlm, GatewayClient, LlmClient, set_llm
from firstlook_core.migrate import migrate, reset
from firstlook_core.tenants import create_tenant, create_user
from firstlook_ingest.connectors.base import RawItem
from firstlook_ingest.crm import import_records, parse_csv
from firstlook_ingest.raw import land

from .fund import FundFixture, harbor, savanna

_ID = re.compile(r'<interaction id="<([^@>]+)@fixtures\.firstlook\.local>"')


def golden_llm(fixtures: list[FundFixture]) -> FakeLlm:
    golden = {e.key: e.golden for f in fixtures for e in f.emails}

    def respond(task: str, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        m = _ID.search(user)
        return golden.get(m.group(1), {}) if m else {"intros": [], "next_steps": [], "deal_mentions": []}

    return FakeLlm(responder=respond)


def _drain(bus: InMemoryBus) -> None:
    """Relay the outbox and run consumers until no events remain."""
    from firstlook_ai.consumer import handle as ai_handle
    from firstlook_resolver.consumer import handle as resolver_handle

    while True:
        with system_tx() as conn:
            relayed = outbox.relay_once(conn, bus)
        handled = bus.consume([outbox.Topics.RAW_INTERACTION], "resolver", resolver_handle)
        handled += bus.consume([outbox.Topics.INTERACTION_RESOLVED], "ai-extraction", ai_handle)
        if relayed == 0 and handled == 0:
            return


def seed_fund(fixture: FundFixture, bus: InMemoryBus) -> UUID:
    with system_tx() as conn:
        existing = conn.execute("SELECT id FROM tenants WHERE slug = %s", (fixture.slug,)).fetchone()
    if existing:
        print(f"  {fixture.name}: already seeded (use --reset to rebuild)")
        return existing["id"]

    with tenant_tx("00000000-0000-0000-0000-000000000000") as conn:
        tenant_id = create_tenant(conn, fixture.name, fixture.slug)

    accounts: dict[str, UUID] = {}
    with tenant_tx(tenant_id) as conn:
        for email, name, role in fixture.team:
            user_id, _ = create_user(conn, tenant_id, email, name, role)
            accounts[email] = conn.execute(
                "INSERT INTO connector_accounts (tenant_id, user_id, provider, account_email, status)"
                " VALUES (%s, %s, 'fixture', %s, 'paused') RETURNING id",
                (tenant_id, user_id, email),
            ).fetchone()["id"]

    with tenant_tx(tenant_id) as conn:
        for e in fixture.emails:
            land(
                conn,
                tenant_id,
                "fixture",
                RawItem("email", f"fixture:{e.key}", e.raw, "message/rfc822"),
                account_id=accounts[e.owner],
            )
        for owner, event in fixture.meetings:
            land(
                conn,
                tenant_id,
                "fixture",
                RawItem("meeting", event["id"], json.dumps(event).encode(), "application/json"),
                account_id=accounts[owner],
            )
        for owner, transcript in fixture.transcripts:
            land(
                conn,
                tenant_id,
                "fixture",
                RawItem("transcript", transcript["id"], json.dumps(transcript).encode(), "application/json"),
                account_id=accounts[owner],
            )
    _drain(bus)

    admin = next(email for email, _, role in fixture.team if role == "admin")
    with tenant_tx(tenant_id) as conn:
        admin_id = conn.execute("SELECT id FROM users WHERE email = %s", (admin,)).fetchone()["id"]
        for vendor, object_type, text in fixture.crm_csv:
            data = text.encode()
            source_id = land(
                conn,
                tenant_id,
                f"crm_{vendor}",
                RawItem("crm_export", f"csv:{hashlib.sha256(data).hexdigest()}", data, "text/csv"),
            )
            import_records(
                conn,
                tenant_id,
                vendor,
                parse_csv(data, vendor, object_type),
                source_id=source_id,
                actor_id=admin_id,
            )
    _drain(bus)

    with tenant_tx(tenant_id) as conn:
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM interactions) AS interactions,"
            " (SELECT count(*) FROM people p JOIN entities e ON e.id = p.id WHERE e.merged_into IS NULL) AS people,"
            " (SELECT count(*) FROM companies) AS companies,"
            " (SELECT count(*) FROM extractions) AS extractions,"
            " (SELECT count(*) FROM er_candidates WHERE status = 'pending') AS review,"
            " (SELECT count(*) FROM edges WHERE type = 'knows' AND valid_to IS NULL) AS knows"
        ).fetchone()
    print(f"  {fixture.name}: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return tenant_id


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firstlook-seed")
    parser.add_argument("--reset", action="store_true", help="drop and recreate the database first")
    parser.add_argument(
        "--llm",
        choices=["golden", "gateway"],
        default="golden",
        help="golden: fixture annotations (no model calls); gateway: real extraction",
    )
    args = parser.parse_args(argv)

    if args.reset:
        reset()
    migrate(verbose=False)

    fixtures = [savanna(), harbor()]
    llm: LlmClient = golden_llm(fixtures) if args.llm == "golden" else GatewayClient()
    set_llm(llm)
    bus = InMemoryBus()
    print(f"Seeding ({args.llm} extractions):")
    for fixture in fixtures:
        seed_fund(fixture, bus)
    print("\nSign in at http://localhost:13000/login with any of:")
    for f in fixtures:
        for email, name, role in f.team:
            print(f"  {email:<24} {name} ({role}, {f.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
