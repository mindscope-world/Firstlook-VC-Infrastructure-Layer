"""Bus consumer for AI extraction.

    interactions.resolved -> proposed extractions (intros, next steps, deals)
    documents.parsed      -> proposed fact sheet

uv run python -m firstlook_ai.consumer
"""

from __future__ import annotations

import logging
from uuid import UUID

from firstlook_core.adapters.bus import Event, run_consumer
from firstlook_core.db import tenant_tx
from firstlook_core.llm import BudgetExceeded
from firstlook_core.outbox import Topics

from .extraction import extract_interaction
from .factsheet import extract_fact_sheet

log = logging.getLogger("firstlook.ai")

EXTRACTABLE = {"email", "transcript", "meeting", "note"}


def handle(event: Event) -> list[UUID]:
    p = event.payload
    if event.topic == Topics.DOCUMENT_PARSED:
        return handle_document(event)
    if p.get("kind") not in EXTRACTABLE:
        return []
    tenant_id = UUID(p["tenant_id"])
    try:
        with tenant_tx(tenant_id) as conn:
            ids = extract_interaction(conn, tenant_id, p["interaction_id"])
    except BudgetExceeded as e:
        # Not retried: the interaction can be re-extracted once budget allows.
        log.warning("skipping extraction for %s: %s", p["interaction_id"], e)
        return []
    log.info("interaction %s -> %d extractions", p["interaction_id"], len(ids))
    return ids


def handle_document(event: Event) -> list[UUID]:
    p = event.payload
    tenant_id = UUID(p["tenant_id"])
    try:
        with tenant_tx(tenant_id) as conn:
            sheet = extract_fact_sheet(conn, tenant_id, p["document_id"])
    except BudgetExceeded as e:
        log.warning("skipping fact sheet for document %s: %s", p["document_id"], e)
        return []
    log.info("document %s -> fact sheet %s", p["document_id"], sheet)
    return [sheet] if sheet else []


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_consumer([Topics.INTERACTION_RESOLVED, Topics.DOCUMENT_PARSED], "ai-extraction", handle)


if __name__ == "__main__":
    main()
