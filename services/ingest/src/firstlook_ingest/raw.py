"""Land raw items: encrypted object storage + a sources row + an outbox event."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

import psycopg

from firstlook_core import outbox
from firstlook_core.objects import TenantObjects

from .connectors.base import RawItem

_SUFFIX = {"message/rfc822": ".eml", "application/json": ".json", "text/csv": ".csv"}


def land(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    connector: str,
    item: RawItem,
    *,
    account_id: UUID | str | None = None,
    objects: TenantObjects | None = None,
) -> UUID | None:
    """Store one raw item. Returns the new source id, or None if this
    (connector, external_id) was already ingested."""
    objects = objects or TenantObjects(conn, tenant_id)
    uri = objects.put(
        f"raw/{connector}/{item.kind}", item.data, item.content_type, _SUFFIX.get(item.content_type, "")
    )
    row = conn.execute(
        "INSERT INTO sources (tenant_id, connector, connector_account_id, external_id, raw_object_uri, content_hash)"
        " VALUES (%s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (tenant_id, connector, external_id) DO NOTHING RETURNING id",
        (
            str(tenant_id),
            connector,
            str(account_id) if account_id else None,
            item.external_id,
            uri,
            hashlib.sha256(item.data).hexdigest(),
        ),
    ).fetchone()
    if row is None:
        return None
    payload: dict[str, Any] = {"source_id": str(row["id"]), "kind": item.kind, "connector": connector}
    if item.metadata:
        payload["metadata"] = item.metadata
    outbox.enqueue(conn, tenant_id, outbox.Topics.RAW_INTERACTION, payload, key=str(row["id"]))
    return row["id"]
