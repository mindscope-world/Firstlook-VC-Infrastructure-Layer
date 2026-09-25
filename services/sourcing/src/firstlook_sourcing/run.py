"""Score every tracked company against a thesis and store the ranked run."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from firstlook_core import audit
from firstlook_core.config import get_settings
from firstlook_core.embeddings import to_pgvector
from firstlook_core.llm import BudgetExceeded, LlmClient, get_llm

from .ranker import (
    MIN_LABELS_FOR_LEARNED,
    Candidate,
    LogisticRanker,
    Ranker,
    RulesRanker,
    Scored,
    features,
    train_logistic,
)
from .rerank import CandidateFacts, Fact, rerank

log = logging.getLogger("firstlook.sourcing.run")
MAX_STORED = 500


def _vec(text: str | None) -> list[float] | None:
    return [float(x) for x in text.strip("[]").split(",")] if text else None


def load_thesis(conn: psycopg.Connection, version_id: UUID | str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT v.*, v.embedding::text AS embedding_text, t.name, t.active FROM thesis_versions v"
        " JOIN theses t ON t.id = v.thesis_id WHERE v.id = %s",
        (str(version_id),),
    ).fetchone()
    if row is None:
        raise LookupError(f"thesis version {version_id} not found")
    row["embedding_vec"] = _vec(row.pop("embedding_text"))
    for k in ("cheque_min_usd", "cheque_max_usd"):
        row[k] = float(row[k]) if row[k] is not None else None
    return row


def load_candidates(conn: psycopg.Connection, now: datetime) -> tuple[list[Candidate], dict[Any, dict]]:
    companies = conn.execute(
        """SELECT c.id, c.name, c.domain::text AS domain, c.description, c.sectors, c.stage, c.country,
                  c.founded_year, c.headcount, c.total_raised_usd, c.last_round_usd, c.last_round_at,
                  c.profile_source_id, c.description_embedding::text AS emb,
                  (SELECT d.stage FROM deals d WHERE d.company_id = c.id ORDER BY d.updated_at DESC LIMIT 1) AS deal_stage
             FROM companies c JOIN entities e ON e.id = c.id
            WHERE e.merged_into IS NULL
              -- the fund's own domain and co-investors aren't sourcing targets
              AND NOT EXISTS (SELECT 1 FROM people p WHERE p.company_id = c.id AND p.is_internal)"""
    ).fetchall()
    obs = conn.execute(
        "SELECT company_id, signal, value, source, url, detail, observed_at, source_id FROM signal_observations"
        # Recent signals, plus the full funding history (rounds matter for years).
        " WHERE observed_at >= %s OR signal = 'funding_round_usd' ORDER BY observed_at DESC",
        (now - timedelta(days=400),),
    ).fetchall()
    warm = {
        r["company_id"]: r
        for r in conn.execute(
            """SELECT p.company_id, max((e.props->>'strength')::float) AS strength,
                  (array_agg(pi.full_name || ' knows ' || p.full_name ORDER BY (e.props->>'strength')::float DESC))[1] AS who
             FROM edges e JOIN people p ON p.id = e.dst_id JOIN people pi ON pi.id = e.src_id
             JOIN entities en ON en.id = p.id AND en.merged_into IS NULL
            WHERE e.type = 'knows' AND e.valid_to IS NULL AND p.company_id IS NOT NULL
            GROUP BY p.company_id"""
        ).fetchall()
    }
    touch = {
        r["company_id"]: r
        for r in conn.execute(
            """SELECT p.company_id, count(DISTINCT i.id) AS n, max(i.occurred_at) AS last
             FROM interaction_participants ip JOIN people p ON p.id = ip.person_id
             JOIN interactions i ON i.id = ip.interaction_id
            WHERE p.company_id IS NOT NULL GROUP BY p.company_id"""
        ).fetchall()
    }

    by_company: dict[Any, list[dict]] = defaultdict(list)
    for o in obs:
        by_company[o["company_id"]].append(o)

    candidates, context = [], {}
    for c in companies:
        c["description_vec"] = _vec(c.pop("emb"))
        for k in ("last_round_usd", "total_raised_usd"):
            c[k] = float(c[k]) if c[k] is not None else None
        rows = by_company.get(c["id"], [])
        latest: dict[str, dict] = {}
        for o in rows:
            latest.setdefault(o["signal"], o)
        month_ago = now - timedelta(days=30)
        older_roles = next(
            (o for o in rows if o["signal"] == "open_roles" and o["observed_at"] <= month_ago), None
        )
        news = [
            o for o in rows if o["signal"] == "news_mention" and o["observed_at"] >= now - timedelta(days=90)
        ]
        signals = {k: v["value"] for k, v in latest.items()}
        if older_roles:
            signals["open_roles_30d_ago"] = older_roles["value"]
        signals["news_mentions_90d"] = len({o["url"] for o in news})
        w = warm.get(c["id"])
        candidates.append(Candidate(c, signals, float(w["strength"]) if w else 0.0))
        context[c["id"]] = {
            "latest": latest,
            "news": news[:3],
            "warm": w,
            "touch": touch.get(c["id"]),
            "older_roles": older_roles,
        }
    return candidates, context


def current_ranker(conn: psycopg.Connection, thesis_id: Any) -> Ranker:
    row = conn.execute(
        "SELECT id, weights, labels FROM ranker_models WHERE thesis_id = %s ORDER BY created_at DESC LIMIT 1",
        (thesis_id,),
    ).fetchone()
    if row and row["labels"] >= MIN_LABELS_FOR_LEARNED:
        return LogisticRanker(row["weights"]["weights"], row["weights"]["bias"], str(row["id"]))
    return RulesRanker()


def facts_for(key: str, c: Candidate, ctx: dict[str, Any]) -> CandidateFacts:
    co = c.company
    facts: list[Fact] = []

    def add(text: str, kind: str, url: str = "", source_id: Any = None) -> None:
        facts.append(
            Fact(f"{key}.f{len(facts) + 1}", text, kind, url or "", str(source_id) if source_id else None)
        )

    profile = [
        f"sectors {', '.join(co['sectors'])}" if co["sectors"] else None,
        f"stage {co['stage']}" if co["stage"] else None,
        f"country {co['country']}" if co["country"] else None,
        f"founded {co['founded_year']}" if co["founded_year"] else None,
        f"{co['headcount']} employees" if co["headcount"] else None,
        f"total raised ${co['total_raised_usd']:,.0f}" if co["total_raised_usd"] else None,
    ]
    if any(profile):
        add("Profile: " + "; ".join(p for p in profile if p), "profile", source_id=co["profile_source_id"])
    if co["description"]:
        add(f"Description: {co['description'][:400]}", "profile", source_id=co["profile_source_id"])
    latest = ctx["latest"]
    if (r := latest.get("funding_round_usd")) and r["value"]:
        kind = (r["detail"] or {}).get("type") or (r["detail"] or {}).get("stage") or "round"
        add(
            f"Raised ${r['value']:,.0f} ({kind}) around {r['observed_at']:%Y-%m-%d}",
            "signal",
            r["url"],
            r["source_id"],
        )
    if (r := latest.get("open_roles")) is not None:
        before = ctx["older_roles"]
        trend = f" (was {before['value']:.0f} a month earlier)" if before else ""
        add(f"Open roles: {r['value']:.0f}{trend}", "signal", r["url"])
    if (r := latest.get("github_active_repos_30d")) is not None:
        stars = latest.get("github_stars")
        add(
            f"GitHub: {r['value']:.0f} repos active in the last 30 days"
            + (f", {stars['value']:.0f} stars" if stars else ""),
            "signal",
            r["url"],
        )
    if (r := latest.get("web_visits_monthly")) is not None:
        add(f"Monthly web visits: {r['value']:,.0f}", "signal", r["url"], r["source_id"])
    for n in ctx["news"]:
        add(
            f"News: {(n['detail'] or {}).get('title', 'mention')} ({n['observed_at']:%Y-%m-%d})",
            "news",
            n["url"],
        )
    if ctx["warm"]:
        add(f"Relationship: {ctx['warm']['who']} (strength {ctx['warm']['strength']:.2f})", "relationship")
    if ctx["touch"]:
        add(
            f"The team has {ctx['touch']['n']} interactions with this company, last on "
            f"{ctx['touch']['last']:%Y-%m-%d}",
            "interaction",
        )
    if co.get("deal_stage"):
        add(f"Already in the pipeline at stage {co['deal_stage']}", "interaction")
    return CandidateFacts(key, co["id"], co["name"], facts)


def score_thesis(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    version_id: UUID | str,
    *,
    llm: LlmClient | None = None,
    rerank_top_n: int | None = None,
    now: datetime | None = None,
) -> UUID:
    """Rank all tracked companies for one thesis version. conn: tenant-scoped (service role)."""
    llm = llm or get_llm()
    now = now or datetime.now(UTC)
    top_n = get_settings().sourcing_rerank_top_n if rerank_top_n is None else rerank_top_n
    thesis = load_thesis(conn, version_id)
    if thesis["embedding_vec"] is None and thesis["description"]:
        # Versions created by the TypeScript API arrive without an embedding.
        vec = llm.embed(tenant_id, [thesis["description"]], task="embed.thesis")[0]
        conn.execute(
            "UPDATE thesis_versions SET embedding = %s WHERE id = %s", (to_pgvector(vec), thesis["id"])
        )
        thesis["embedding_vec"] = vec
    ranker = current_ranker(conn, thesis["thesis_id"])
    run_id = conn.execute(
        "INSERT INTO score_runs (tenant_id, thesis_version_id, ranker) VALUES (%s, %s, %s) RETURNING id",
        (str(tenant_id), thesis["id"], ranker.name),
    ).fetchone()["id"]

    candidates, ctx = load_candidates(conn, now)
    by_id = {c.company["id"]: c for c in candidates}
    scored: list[Scored] = []
    excluded = 0
    for c in candidates:
        s = features(c, thesis, now.date())
        if s.excluded:
            excluded += 1
            continue
        s.score = ranker.score(s.features)
        scored.append(s)
    scored.sort(key=lambda s: s.score, reverse=True)

    # Stage 2 on the top N.
    reranked: dict[Any, Any] = {}
    model = None
    head = scored[:top_n]
    if head:
        facts = [facts_for(f"c{i + 1}", by_id[s.company_id], ctx[s.company_id]) for i, s in enumerate(head)]
        try:
            results, model = rerank(llm, tenant_id, thesis, facts)
            reranked = {r.company_id: r for r in results}
        except BudgetExceeded as e:
            log.warning("skipping re-rank: %s", e)

    final: list[tuple[float, Scored]] = []
    for s in scored:
        r = reranked.get(s.company_id)
        final.append(((0.4 * s.score + 0.6 * r.stage2) if r else s.score, s))
    final.sort(key=lambda x: x[0], reverse=True)

    for rank, (score, s) in enumerate(final[:MAX_STORED], start=1):
        r = reranked.get(s.company_id)
        conn.execute(
            "INSERT INTO company_scores (tenant_id, run_id, thesis_version_id, company_id, stage1_score, features,"
            " stage2_score, final_score, rationale, concerns, citations, rank)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(tenant_id),
                run_id,
                thesis["id"],
                s.company_id,
                round(s.score, 4),
                Jsonb(s.features),
                r.stage2 if r else None,
                round(score, 4),
                r.rationale if r else None,
                r.concerns if r else None,
                Jsonb(r.citations if r else []),
                rank,
            ),
        )
    conn.execute(
        "UPDATE score_runs SET status = 'done', finished_at = now(), candidates = %s, scored = %s, reranked = %s,"
        " rerank_model = %s WHERE id = %s",
        (len(candidates), min(len(final), MAX_STORED), len(reranked), model, run_id),
    )
    audit.record(
        conn,
        tenant_id,
        "sourcing.scored",
        "thesis_version",
        thesis["id"],
        actor_type="service",
        details={
            "run_id": str(run_id),
            "ranker": ranker.name,
            "candidates": len(candidates),
            "excluded": excluded,
            "reranked": len(reranked),
            "model": model,
        },
    )
    return run_id


def score_all(conn: psycopg.Connection, tenant_id: UUID | str, **kwargs: Any) -> list[UUID]:
    versions = conn.execute("SELECT id FROM current_thesis_versions WHERE active").fetchall()
    return [score_thesis(conn, tenant_id, v["id"], **kwargs) for v in versions]


def train_for_thesis(
    conn: psycopg.Connection, tenant_id: UUID | str, thesis_id: UUID | str
) -> dict[str, Any] | None:
    """Fit the learned ranker from feedback once there are enough labels."""
    rows = conn.execute(
        "SELECT features, vote FROM sourcing_feedback WHERE thesis_id = %s AND features <> '{}'",
        (str(thesis_id),),
    ).fetchall()
    if len(rows) < MIN_LABELS_FOR_LEARNED or len({r["vote"] for r in rows}) < 2:
        return None
    model, metrics = train_logistic([(r["features"], r["vote"]) for r in rows])
    row = conn.execute(
        "INSERT INTO ranker_models (tenant_id, thesis_id, kind, weights, labels, metrics)"
        " VALUES (%s, %s, 'logistic-v1', %s, %s, %s) RETURNING id",
        (
            str(tenant_id),
            str(thesis_id),
            Jsonb({"weights": model.weights, "bias": model.bias}),
            len(rows),
            Jsonb(metrics),
        ),
    ).fetchone()
    return {"model_id": str(row["id"]), "labels": len(rows), **metrics, **asdict(model)}


def create_thesis(
    conn: psycopg.Connection,
    tenant_id: UUID | str,
    name: str,
    *,
    sectors: list[str],
    stages: list[str],
    geographies: list[str],
    cheque_min_usd: float | None = None,
    cheque_max_usd: float | None = None,
    founder_profile: str = "",
    description: str = "",
    user_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    """Create a thesis with its first version. Returns (thesis_id, version_id)."""
    thesis_id = conn.execute(
        "INSERT INTO theses (tenant_id, name, created_by) VALUES (%s, %s, %s) RETURNING id",
        (str(tenant_id), name, user_id),
    ).fetchone()["id"]
    version_id = conn.execute(
        "INSERT INTO thesis_versions (tenant_id, thesis_id, version, sectors, stages, geographies, cheque_min_usd,"
        " cheque_max_usd, founder_profile, description, created_by)"
        " VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            str(tenant_id),
            thesis_id,
            sectors,
            stages,
            geographies,
            cheque_min_usd,
            cheque_max_usd,
            founder_profile,
            description,
            user_id,
        ),
    ).fetchone()["id"]
    return thesis_id, version_id
