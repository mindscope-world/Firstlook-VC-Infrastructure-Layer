"""Relationship strength.

For each (internal team member, external person) pair that has interacted:

    recency     = 0.5 ** (days_since_last / HALF_LIFE_DAYS)
    frequency   = 1 - exp(-weighted_interactions_in_window / FREQ_SCALE)
    reciprocity = min(outbound, inbound) / max(outbound, inbound)
                  (meetings and calls count in both directions)
    strength    = 0.4 * recency + 0.4 * frequency + 0.2 * reciprocity

Emails weigh 1, meetings/calls/transcripts weigh 3. Results are written as
live `knows` edges (internal -> external) with the components in props.

External people who appear together on interactions (e.g. both CC'd on an
intro) get a weaker, undirected `co_occurs` edge. Those, plus `works_at` and
`introduced` edges, give warm_paths() in the database its second hops.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

HALF_LIFE_DAYS = 45.0
WINDOW_DAYS = 180
FREQ_SCALE = 8.0
KIND_WEIGHT = {"email": 1.0, "message": 1.0, "meeting": 3.0, "call": 3.0, "transcript": 3.0, "note": 0.5}


@dataclass
class PairStats:
    last_at: datetime
    weighted: float = 0.0
    total: int = 0
    outbound: float = 0.0
    inbound: float = 0.0


def score(stats: PairStats, now: datetime) -> dict[str, Any]:
    days = max(0.0, (now - stats.last_at).total_seconds() / 86400)
    recency = 0.5 ** (days / HALF_LIFE_DAYS)
    frequency = 1 - math.exp(-stats.weighted / FREQ_SCALE)
    hi, lo = max(stats.outbound, stats.inbound), min(stats.outbound, stats.inbound)
    reciprocity = lo / hi if hi else 0.0
    strength = 0.4 * recency + 0.4 * frequency + 0.2 * reciprocity
    return {
        "strength": round(strength, 4),
        "recency": round(recency, 4),
        "frequency": round(frequency, 4),
        "reciprocity": round(reciprocity, 4),
        "last_interaction_at": stats.last_at.isoformat(),
        "interactions_window": stats.total,
        "outbound": stats.outbound,
        "inbound": stats.inbound,
    }


def recompute(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    *,
    people: list[UUID] | None = None,
    now: datetime | None = None,
) -> int:
    """Recompute strength for the whole tenant, or only pairs touching `people`.
    conn must be tenant-scoped with the service role. Returns edges written."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=WINDOW_DAYS)
    tenant_id = str(tenant_id)

    filter_sql = ""
    params: dict[str, Any] = {"t": tenant_id, "since": since}
    if people:
        filter_sql = """AND i.id IN (SELECT interaction_id FROM interaction_participants
                                     WHERE tenant_id = %(t)s AND person_id = ANY(%(people)s))"""
        params["people"] = list(people)

    rows = conn.execute(
        f"""
        SELECT i.id, i.kind::text AS kind, i.occurred_at, p.person_id, p.role, pe.is_internal
          FROM interactions i
          JOIN interaction_participants p ON p.interaction_id = i.id
          JOIN people pe ON pe.id = p.person_id
          JOIN entities e ON e.id = p.person_id AND e.merged_into IS NULL
         WHERE i.tenant_id = %(t)s AND i.occurred_at >= %(since)s {filter_sql}
         ORDER BY i.id
        """,
        params,
    ).fetchall()

    by_interaction: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_interaction[r["id"]].append(r)

    pairs: dict[tuple[UUID, UUID], PairStats] = {}
    co: dict[tuple[UUID, UUID], PairStats] = {}
    for parts in by_interaction.values():
        kind, at = parts[0]["kind"], parts[0]["occurred_at"]
        weight = KIND_WEIGHT.get(kind, 1.0)
        mutual = kind in ("meeting", "call", "transcript")
        senders = {p["person_id"] for p in parts if p["role"] in ("from", "organizer")}
        internal = {p["person_id"] for p in parts if p["is_internal"]}
        external = {p["person_id"] for p in parts if not p["is_internal"]}

        for i in internal:
            for x in external:
                st = pairs.get((i, x))
                if st is None:
                    st = pairs[(i, x)] = PairStats(last_at=at)
                st.last_at = max(st.last_at, at)
                st.weighted += weight
                st.total += 1
                if mutual:
                    st.outbound += 1
                    st.inbound += 1
                elif i in senders:
                    st.outbound += 1
                elif x in senders:
                    st.inbound += 1

        ext = sorted(external, key=str)
        for a_idx, a in enumerate(ext):
            for b in ext[a_idx + 1 :]:
                st = co.get((a, b))
                if st is None:
                    st = co[(a, b)] = PairStats(last_at=at)
                st.last_at = max(st.last_at, at)
                st.weighted += weight
                st.total += 1
                st.outbound += 1
                st.inbound += 1

    # With a people filter, only pairs touching those people saw all of their
    # interactions; other pairs in the result are partial and must not be written.
    wanted = set(people) if people else None

    def complete(a: UUID, b: UUID) -> bool:
        return wanted is None or a in wanted or b in wanted

    written = 0
    for (src, dst), st in pairs.items():
        if not complete(src, dst):
            continue
        _upsert_edge(conn, tenant_id, src, dst, "knows", score(st, now))
        written += 1
    for (a, b), st in co.items():
        if not complete(a, b):
            continue
        props = score(st, now)
        # Co-occurrence is weaker evidence than direct correspondence.
        props["strength"] = round(props["strength"] * 0.6, 4)
        _upsert_edge(conn, tenant_id, a, b, "co_occurs", props)
        written += 1
    return written


def _upsert_edge(
    conn: psycopg.Connection, tenant_id: str, src: UUID, dst: UUID, type_: str, props: dict
) -> None:
    conn.execute(
        """
        INSERT INTO edges (tenant_id, src_id, dst_id, type, props, confidence)
        VALUES (%s, %s, %s, %s, %s, 1.0)
        ON CONFLICT (tenant_id, src_id, dst_id, type) WHERE valid_to IS NULL
        DO UPDATE SET props = EXCLUDED.props, updated_at = now()
        """,
        (tenant_id, src, dst, type_, Jsonb(props)),
    )
