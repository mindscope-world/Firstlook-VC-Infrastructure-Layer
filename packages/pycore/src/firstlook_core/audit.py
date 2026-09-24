"""Append-only audit trail. Every data access by the AI layer, every prompt,
and every agent or user action that changes state writes an event."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb


def record(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    action: str,
    resource_type: str,
    resource_id: str | UUID | None = None,
    *,
    actor_type: str = "service",
    actor_id: UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, details)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (
            str(tenant_id),
            actor_type,
            str(actor_id) if actor_id else None,
            action,
            resource_type,
            str(resource_id) if resource_id else None,
            Jsonb(details or {}),
        ),
    )
