"""Transactional outbox: publish events atomically with the change that caused
them. `enqueue` inside the business transaction; `relay_once` (run by the
outbox relay process) moves rows to the event bus."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .adapters.bus import EventBus


class Topics:
    RAW_INTERACTION = "interactions.raw"  # a new raw object is stored
    INTERACTION_RESOLVED = "interactions.resolved"  # parsed + entities resolved
    EXTRACTIONS_CREATED = "extractions.created"
    DEAL_EVENTS = "deals.events"
    CONNECTOR_EVENTS = "connectors.events"


def enqueue(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    topic: str,
    payload: dict[str, Any],
    key: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO outbox (tenant_id, topic, key, payload) VALUES (%s, %s, %s, %s)",
        (str(tenant_id), topic, key, Jsonb({**payload, "tenant_id": str(tenant_id)})),
    )


def relay_once(conn: psycopg.Connection, bus: EventBus, batch: int = 500) -> int:
    """Publish one batch. conn must be a system (BYPASSRLS) connection.
    SKIP LOCKED lets several relays run without double-publishing."""
    rows = conn.execute(
        "SELECT id, topic, key, payload FROM outbox WHERE published_at IS NULL"
        " ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED",
        (batch,),
    ).fetchall()
    for row in rows:
        bus.publish(row["topic"], row["payload"], key=row["key"])
    bus.flush()
    if rows:
        conn.execute("UPDATE outbox SET published_at = now() WHERE id = ANY(%s)", ([r["id"] for r in rows],))
    return len(rows)
