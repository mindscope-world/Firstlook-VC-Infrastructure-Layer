"""Bus consumer for documents.

interactions.resolved -> promote deck/model attachments to documents
documents.stored      -> parse into pages (with OCR for scans)

uv run python -m firstlook_documents.consumer
"""

from __future__ import annotations

import logging
from uuid import UUID

from firstlook_core.adapters.bus import Event, run_consumer
from firstlook_core.db import tenant_tx
from firstlook_core.outbox import Topics

from .store import documents_from_interaction, parse_document

log = logging.getLogger("firstlook.documents")


def handle(event: Event) -> None:
    p = event.payload
    tenant_id = UUID(p["tenant_id"])
    if event.topic == Topics.INTERACTION_RESOLVED:
        if p.get("kind") != "email":
            return
        with tenant_tx(tenant_id) as conn:
            ids = documents_from_interaction(conn, tenant_id, p["interaction_id"])
        if ids:
            log.info("interaction %s -> %d document(s)", p["interaction_id"], len(ids))
        return
    if event.topic == Topics.DOCUMENT_STORED:
        with tenant_tx(tenant_id) as conn:
            status = parse_document(conn, tenant_id, p["document_id"])
        log.info("document %s -> %s", p["document_id"], status)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_consumer([Topics.INTERACTION_RESOLVED, Topics.DOCUMENT_STORED], "documents", handle)


if __name__ == "__main__":
    main()
