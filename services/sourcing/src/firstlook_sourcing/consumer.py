"""Bus consumer: sourcing requests from the API (thesis saved, "Re-run"),
and learning from feedback.

    uv run python -m firstlook_sourcing.consumer
"""

from __future__ import annotations

import logging
from uuid import UUID

from firstlook_core.adapters.bus import Event, run_consumer
from firstlook_core.db import tenant_tx

from .run import train_for_thesis
from .service import collect_tenant, score_tenant

log = logging.getLogger("firstlook.sourcing.consumer")
TOPIC_REQUESTED = "sourcing.requested"
TOPIC_FEEDBACK = "sourcing.feedback"


def handle(event: Event) -> None:
    p = event.payload
    tenant_id = UUID(p["tenant_id"])
    if event.topic == TOPIC_FEEDBACK:
        with tenant_tx(tenant_id) as conn:
            trained = train_for_thesis(conn, tenant_id, p["thesis_id"])
        if trained:
            log.info("retrained ranker for thesis %s on %d labels", p["thesis_id"], trained["labels"])
            score_tenant(tenant_id)
        return
    if p.get("collect"):
        stats = collect_tenant(tenant_id)
        log.info("collected for %s: %s", tenant_id, stats)
    runs = score_tenant(tenant_id, p.get("thesis_version_id"))
    log.info("scored %s -> runs %s", tenant_id, runs)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_consumer([TOPIC_REQUESTED, TOPIC_FEEDBACK], "sourcing", handle)


if __name__ == "__main__":
    main()
