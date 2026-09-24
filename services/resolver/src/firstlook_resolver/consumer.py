"""Bus consumer: interactions.raw -> resolved interactions.

uv run python -m firstlook_resolver.consumer
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from firstlook_core.adapters.bus import Event, run_consumer
from firstlook_core.db import tenant_tx
from firstlook_core.objects import TenantObjects
from firstlook_core.outbox import Topics

from .pipeline import Pipeline, ProcessResult

log = logging.getLogger("firstlook.resolver")


def handle(event: Event) -> ProcessResult | None:
    p = event.payload
    tenant_id = UUID(p["tenant_id"])
    with tenant_tx(tenant_id) as conn:
        source = conn.execute(
            "SELECT s.id, s.raw_object_uri, s.connector, ca.user_id, ca.settings"
            " FROM sources s LEFT JOIN connector_accounts ca ON ca.id = s.connector_account_id"
            " WHERE s.id = %s",
            (p["source_id"],),
        ).fetchone()
        if source is None:
            log.warning("source %s not found (tenant %s)", p["source_id"], tenant_id)
            return None
        objects = TenantObjects(conn, tenant_id)
        raw = objects.get(source["raw_object_uri"])
        settings = source["settings"] or {}
        visibility = settings.get("default_visibility", "team")
        pipeline = Pipeline(conn, tenant_id, objects=objects)
        kind = p["kind"]
        kwargs = {"source_id": source["id"], "owner_user_id": source["user_id"], "visibility": visibility}
        if kind == "email":
            result = pipeline.process_email(raw, **kwargs, extra_metadata=p.get("metadata"))
        elif kind == "meeting":
            result = pipeline.process_meeting(json.loads(raw), **kwargs)
        elif kind == "transcript":
            result = pipeline.process_transcript(json.loads(raw), **kwargs)
        else:
            log.info("no resolver handler for kind %s", kind)
            return None
    log.info("processed %s source=%s -> %s", kind, p["source_id"], result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run_consumer([Topics.RAW_INTERACTION], "resolver", handle)


if __name__ == "__main__":
    main()
