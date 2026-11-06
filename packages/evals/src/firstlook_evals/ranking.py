"""Sourcing-ranking eval: NDCG of stage 1 (rules) and of the final order after
the stage-2 LLM re-rank, against graded relevance labels.

Uses the production code paths without a database: `features` and the rules
ranker for stage 1, `facts_for` to build the evidence the model sees, `rerank`
for stage 2 and `final_score` to blend them.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from firstlook_core.embeddings import hash_embed
from firstlook_core.llm import LlmClient

from .base import SuiteResult, load_yaml
from .metrics import ndcg


def _at(d: date) -> datetime:
    return datetime.combine(d, time(9))


def _candidate(i: int, c: dict[str, Any]):
    from firstlook_sourcing.ranker import Candidate

    funding = c.get("funding") or {}
    company = {
        "id": f"co{i}",
        "name": c["name"],
        "sectors": c.get("sectors", []),
        "stage": c.get("stage"),
        "country": c.get("country"),
        "founded_year": c.get("founded_year"),
        "headcount": c.get("headcount"),
        "total_raised_usd": funding.get("usd"),
        "last_round_usd": funding.get("usd"),
        "last_round_at": funding.get("date"),
        "description": c.get("description"),
        "description_vec": hash_embed(c["description"]) if c.get("description") else None,
        "profile_source_id": None,
        "deal_stage": c.get("deal_stage"),
    }
    latest: dict[str, dict[str, Any]] = {}

    def obs(signal: str, value: float, when: date, **detail: Any) -> None:
        latest[signal] = {
            "value": value,
            "detail": detail,
            "url": "",
            "source_id": None,
            "observed_at": _at(when),
        }

    if funding:
        obs("funding_round_usd", funding["usd"], funding["date"], type=funding.get("type"))
    if c.get("open_roles") is not None:
        obs("open_roles", c["open_roles"], date.today())
    if c.get("github_repos") is not None:
        obs("github_active_repos_30d", c["github_repos"], date.today())
    news = [
        {
            "detail": {"title": n["title"]},
            "observed_at": _at(n["date"]),
            "url": f"https://news.example/{i}/{j}",
        }
        for j, n in enumerate(c.get("news", []))
    ]
    signals = {k: v["value"] for k, v in latest.items()}
    older = None
    if c.get("open_roles_before") is not None:
        signals["open_roles_30d_ago"] = c["open_roles_before"]
        older = {"value": c["open_roles_before"]}
    signals["news_mentions_90d"] = len(news)
    warm = c.get("warm")
    ctx = {"latest": latest, "news": news, "warm": warm, "touch": None, "older_roles": older}
    return Candidate(company, signals, float(warm["strength"]) if warm else 0.0), ctx


def run(llm: LlmClient, tenant_id: Any, mode: str, top_n: int = 20, **_: Any) -> SuiteResult:
    from firstlook_sourcing.ranker import RulesRanker, features
    from firstlook_sourcing.rerank import rerank
    from firstlook_sourcing.run import facts_for, final_score

    golden = load_yaml("ranking.yaml")
    today: date = golden["as_of"]
    thesis = {**golden["thesis"], "embedding_vec": hash_embed(golden["thesis"]["description"])}
    relevance: dict[str, float] = {}
    pool = []
    for i, c in enumerate(golden["companies"]):
        cand, ctx = _candidate(i, c)
        relevance[cand.company["id"]] = c["relevance"]
        pool.append((cand, ctx))

    ranker = RulesRanker()
    scored, excluded = [], []
    for cand, ctx in pool:
        s = features(cand, thesis, today)
        if s.excluded:
            excluded.append((cand, s.excluded))
            continue
        s.score = ranker.score(s.features)
        scored.append((s, cand, ctx))
    scored.sort(key=lambda x: x[0].score, reverse=True)

    all_rel = list(relevance.values())
    stage1_rel = [relevance[s.company_id] for s, _, _ in scored]
    metrics: dict[str, float] = {
        "stage1_ndcg@5": ndcg(stage1_rel, all_rel, 5),
        "stage1_ndcg@10": ndcg(stage1_rel, all_rel, 10),
        "relevant_kept": 1.0
        - sum(1 for c, _ in excluded if relevance[c.company["id"]] >= 2)
        / max(1, sum(1 for r in all_rel if r >= 2)),
    }

    head = scored[:top_n]
    facts = [facts_for(f"c{k + 1}", cand, ctx) for k, (_, cand, ctx) in enumerate(head)]
    results, model = rerank(llm, tenant_id, thesis, facts)
    by_id = {r.company_id: r for r in results}
    final = sorted(
        scored,
        key=lambda x: final_score(
            x[0].score, by_id[x[0].company_id].stage2 if x[0].company_id in by_id else None
        ),
        reverse=True,
    )
    final_rel = [relevance[s.company_id] for s, _, _ in final]
    metrics["final_ndcg@5"] = ndcg(final_rel, all_rel, 5)
    metrics["final_ndcg@10"] = ndcg(final_rel, all_rel, 10)
    metrics["rerank_coverage"] = len(results) / len(head) if head else 1.0
    metrics["rerank_cited"] = sum(1 for r in results if r.citations) / len(results) if results else 0.0

    names = {cand.company["id"]: cand.company["name"] for cand, _ in pool}
    cases = [
        {
            "company": names[s.company_id],
            "relevance": relevance[s.company_id],
            "stage1": round(s.score, 3),
            "stage2": round(by_id[s.company_id].stage2, 3) if s.company_id in by_id else None,
            "rationale": by_id[s.company_id].rationale if s.company_id in by_id else "",
        }
        for s, _, _ in final
    ] + [
        {"company": cand.company["name"], "relevance": relevance[cand.company["id"]], "excluded": why}
        for cand, why in excluded
    ]
    return SuiteResult("ranking", mode, metrics, cases, model=model)
