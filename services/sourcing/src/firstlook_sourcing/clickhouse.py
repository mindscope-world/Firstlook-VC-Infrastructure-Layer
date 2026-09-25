"""Mirror signal observations to ClickHouse for analytics (plan: daily
schedules write to ClickHouse). Postgres stays the source ranking reads, so a
ClickHouse outage only delays analytics."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from firstlook_core.config import get_settings

log = logging.getLogger("firstlook.sourcing.clickhouse")


class ClickHouseMirror:
    def __init__(self, url: str | None = None, http: httpx.Client | None = None):
        s = get_settings()
        self.url = url if url is not None else s.clickhouse_url
        self.http = http or httpx.Client(timeout=15, auth=(s.clickhouse_user, s.clickhouse_password))

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def write(self, rows: list[dict[str, Any]]) -> int:
        if not self.enabled or not rows:
            return 0
        body = "\n".join(json.dumps(r, default=str) for r in rows)
        try:
            r = self.http.post(
                self.url,
                params={"query": "INSERT INTO firstlook.company_signals FORMAT JSONEachRow"},
                content=body.encode(),
            )
            r.raise_for_status()
            return len(rows)
        except httpx.HTTPError as e:
            log.warning("clickhouse mirror failed (%d rows): %s", len(rows), e)
            return 0
