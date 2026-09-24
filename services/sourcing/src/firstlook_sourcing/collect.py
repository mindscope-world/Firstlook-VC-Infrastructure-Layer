"""Collect companies and signals for one tenant.

discover()  finds candidates: vendor search per active thesis, funding news
enrich()    refreshes tracked companies: vendor profile, GitHub, job boards,
            news mentions

Every company goes through entity resolution, so a startup the team already
emailed is enriched in place rather than duplicated. Profile fields from a
licensed vendor or registry overwrite; other sources only fill blanks.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from firstlook_core.embeddings import to_pgvector
from firstlook_core.llm import LlmClient, get_llm
from firstlook_core.objects import TenantObjects
from firstlook_resolver.er import Resolver

from .clickhouse import ClickHouseMirror
from .model import CompanyProfile, Observation
from .sources.github import GitHubSource
from .sources.jobs import JobBoardSource
from .sources.news import NewsItem, NewsSource
from .sources.vendor import VendorQuery, VendorSource

log = logging.getLogger("firstlook.sourcing.collect")

AUTHORITATIVE = ("vendor:", "registry:")


@dataclass
class CollectStats:
    discovered: int = 0
    enriched: int = 0
    observations: int = 0
    errors: list[str] = field(default_factory=list)


class Collector:
    def __init__(
        self,
        conn: psycopg.Connection,
        tenant_id: UUID | str,
        *,
        vendor: VendorSource | None = None,
        github: GitHubSource | None = None,
        jobs: JobBoardSource | None = None,
        news: NewsSource | None = None,
        llm: LlmClient | None = None,
        clickhouse: ClickHouseMirror | None = None,
        objects: TenantObjects | None = None,
    ):
        self.conn = conn
        self.tenant_id = str(tenant_id)
        self.vendor, self.github, self.jobs, self.news = vendor, github, jobs, news
        self.llm = llm or get_llm()
        self.resolver = Resolver(conn, tenant_id, self.llm)
        self.clickhouse = clickhouse or ClickHouseMirror()
        self._objects = objects
        self.stats = CollectStats()

    @property
    def objects(self) -> TenantObjects:
        if self._objects is None:
            self._objects = TenantObjects(self.conn, self.tenant_id)
        return self._objects

    # -- storage -----------------------------------------------------------------

    def _source_row(self, connector: str, ref: str, raw: Any) -> UUID:
        """Snapshot the raw record (one per source, ref and day) for provenance."""
        data = json.dumps(raw, default=str, sort_keys=True).encode()
        uri = self.objects.put(f"raw/{connector.replace(':', '_')}", data, "application/json", ".json")
        external_id = f"{ref}@{date.today().isoformat()}"
        row = self.conn.execute(
            "INSERT INTO sources (tenant_id, connector, external_id, raw_object_uri) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (tenant_id, connector, external_id) DO UPDATE SET raw_object_uri = EXCLUDED.raw_object_uri"
            " RETURNING id",
            (self.tenant_id, connector, external_id, uri),
        ).fetchone()
        return row["id"]

    def upsert_profile(self, p: CompanyProfile, raw: Any = None) -> UUID | None:
        source_id = self._source_row(p.source or "unknown", p.source_ref or p.name, raw or p.__dict__)
        res = self.resolver.resolve_company(
            name=p.name,
            domain=p.domain,
            registry_id=p.registry_id,
            source_id=source_id,
            country=p.country,
            description=p.description,
        )
        if res is None:
            return None
        cid = res.entity_id
        current = self.conn.execute(
            "SELECT description, sectors, description_embedding IS NULL AS no_emb FROM companies WHERE id = %s",
            (cid,),
        ).fetchone()
        authoritative = p.source.startswith(AUTHORITATIVE)

        def pick(col: str) -> str:
            return (
                f"{col} = coalesce(%({col})s, {col})"
                if authoritative
                else f"{col} = coalesce({col}, %({col})s)"
            )

        cols = [
            "stage",
            "country",
            "founded_year",
            "headcount",
            "total_raised_usd",
            "last_round_usd",
            "last_round_at",
            "github_org",
            "jobs_board",
            "description",
        ]
        params = {c: getattr(p, c) for c in cols} | {"id": cid, "sectors": p.sectors, "source_id": source_id}
        self.conn.execute(
            f"UPDATE companies SET {', '.join(pick(c) for c in cols)},"
            " sectors = ARRAY(SELECT DISTINCT unnest(sectors || %(sectors)s::text[])),"
            " profile_source_id = %(source_id)s, profile_updated_at = now() WHERE id = %(id)s",
            params,
        )
        new_desc = p.description if (authoritative or not current["description"]) else current["description"]
        if new_desc and (current["no_emb"] or new_desc != current["description"]):
            vec = self.llm.embed(self.tenant_id, [new_desc], task="embed.company_description")[0]
            self.conn.execute(
                "UPDATE companies SET description_embedding = %s WHERE id = %s", (to_pgvector(vec), cid)
            )
        for f in p.founders:
            person = self.resolver.resolve_person(
                email=f.get("email") or None,
                name=f.get("name"),
                title=f.get("title"),
                company_id=cid,
                source_id=source_id,
                context=f"{p.source} profile",
            )
            if person:
                self.resolver.link_works_at(person.entity_id, cid, source_id, f.get("title"))
        return cid

    def record(self, company_id: UUID, observations: list[Observation], source_id: UUID | None = None) -> int:
        written, mirror = 0, []
        for o in observations:
            at = o.observed_at or datetime.now(UTC)
            row = self.conn.execute(
                "INSERT INTO signal_observations (tenant_id, company_id, signal, value, source, source_id, url, detail,"
                " observed_at, observed_on) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (tenant_id, company_id, signal, source, observed_on, url) DO NOTHING RETURNING id",
                (
                    self.tenant_id,
                    company_id,
                    o.signal,
                    o.value,
                    o.source,
                    source_id,
                    o.url,
                    Jsonb(o.detail),
                    at,
                    at.astimezone(UTC).date(),
                ),
            ).fetchone()
            if row:
                written += 1
                mirror.append(
                    {
                        "tenant_id": self.tenant_id,
                        "company_id": str(company_id),
                        "signal": o.signal,
                        "value": o.value,
                        "source": o.source,
                        "observed_at": at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    }
                )
        self.clickhouse.write(mirror)
        self.stats.observations += written
        return written

    # -- discovery -----------------------------------------------------------------

    def discover(self, news_items: list[NewsItem] | None = None) -> None:
        if self.vendor:
            theses = self.conn.execute(
                "SELECT sectors, stages, geographies FROM current_thesis_versions WHERE active"
            ).fetchall()
            for t in theses:
                q = VendorQuery(sectors=t["sectors"], stages=t["stages"], geographies=t["geographies"])
                try:
                    for rec in self.vendor.search(q):
                        cid = self.upsert_profile(rec.profile, rec.raw)
                        if cid:
                            self.record(
                                cid,
                                rec.observations,
                                self.conn.execute(
                                    "SELECT profile_source_id FROM companies WHERE id = %s", (cid,)
                                ).fetchone()["profile_source_id"],
                            )
                            self.stats.discovered += 1
                except Exception as e:  # noqa: BLE001 - one bad source shouldn't stop the run
                    log.exception("vendor search failed")
                    self.stats.errors.append(f"vendor: {e}")
        if news_items:
            for profile, obs in NewsSource.funding_announcements(news_items):
                cid = self.upsert_profile(profile, {"title": obs.detail.get("title"), "url": obs.url})
                if cid:
                    self.record(cid, [obs])
                    self.stats.discovered += 1

    # -- enrichment ------------------------------------------------------------------

    def tracked(self) -> list[dict[str, Any]]:
        return self.conn.execute(
            "SELECT c.id, c.name, c.domain::text AS domain, c.github_org, c.jobs_board FROM companies c"
            " JOIN entities e ON e.id = c.id WHERE e.merged_into IS NULL ORDER BY c.name"
        ).fetchall()

    def enrich(self, news_items: list[NewsItem] | None = None) -> None:
        companies = self.tracked()
        for c in companies:
            try:
                if self.vendor and c["domain"]:
                    rec = self.vendor.lookup(c["domain"])
                    if rec:
                        cid = self.upsert_profile(rec.profile, rec.raw)
                        if cid:
                            self.record(cid, rec.observations)
                            c = {
                                **c,
                                **self.conn.execute(
                                    "SELECT github_org, jobs_board FROM companies WHERE id = %s", (cid,)
                                ).fetchone(),
                            }
                if self.github and c["github_org"]:
                    self.record(c["id"], self.github.observe(c["github_org"]))
                if self.jobs and c["jobs_board"]:
                    self.record(c["id"], self.jobs.observe(c["jobs_board"]))
                self.stats.enriched += 1
            except Exception as e:  # noqa: BLE001
                log.warning("enrich %s failed: %s", c["name"], e)
                self.stats.errors.append(f"{c['name']}: {e}")
        if news_items:
            names = {str(c["id"]): c["name"] for c in companies}
            for cid, obs in NewsSource.mentions(news_items, names).items():
                self.record(UUID(cid), obs)


def import_registry(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    csv_text: str,
    registry: str = "ke-brs",
    country: str = "KE",
    llm: LlmClient | None = None,
) -> CollectStats:
    """Load a registry extract (see sources/registry.py)."""
    from .sources.registry import parse_registry_csv

    collector = Collector(conn, tenant_id, llm=llm)
    for profile, obs in parse_registry_csv(csv_text, registry, country):
        cid = collector.upsert_profile(profile)
        if cid:
            collector.record(cid, [obs])
            collector.stats.discovered += 1
    return collector.stats
