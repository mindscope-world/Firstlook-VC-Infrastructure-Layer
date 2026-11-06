"""Entity-resolution eval: run the real resolver over the golden mentions.

Each section (people, companies) runs in its own throwaway tenant against the
local Postgres, so the resolver's SQL candidate search, identifiers and review
queue are all exercised. Embeddings use the deterministic local embedder (the
gateway's default too), so this suite needs no model and is reproducible.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from firstlook_core.llm import FakeLlm

from .base import SuiteResult, load_yaml, scratch_tenant
from .metrics import pairwise_clustering


def _label(m: dict[str, Any]) -> str:
    parts = [m.get("name") or "", f"<{m['email']}>" if m.get("email") else ""]
    parts += [m["domain"] if m.get("domain") else "", m.get("registry_id") or "", m.get("crm_id") or ""]
    return " ".join(p for p in parts if p)


def _resolve_section(kind: str, mentions: list[dict[str, Any]], team: list[list[str]]) -> dict[str, Any]:
    from firstlook_core.db import tenant_tx
    from firstlook_core.tenants import create_user
    from firstlook_resolver.er import Resolver

    llm = FakeLlm()
    predicted: dict[int, Any] = {}
    gold: dict[int, Any] = {}
    rows: list[dict[str, Any]] = []
    null_violations = 0
    with scratch_tenant(f"er-{kind}") as tenant_id, tenant_tx(tenant_id) as conn:
        for email, name, role in team if kind == "people" else []:
            create_user(conn, tenant_id, email, name, role)
        r = Resolver(conn, tenant_id, llm)
        for i, m in enumerate(mentions):
            if kind == "people":
                res = r.resolve_person(
                    email=m.get("email"), name=m.get("name"), crm_id=m.get("crm_id"), context="eval"
                )
            else:
                res = r.resolve_company(
                    name=m.get("name"), domain=m.get("domain"), registry_id=m.get("registry_id")
                )
            if m["gold"] is None:
                null_violations += res is not None
                continue
            if res is None:
                raise AssertionError(f"resolver returned nothing for {_label(m)}")
            predicted[i], gold[i] = res.entity_id, m["gold"]
            rows.append(
                {
                    "mention": _label(m),
                    "gold": m["gold"],
                    "entity": str(res.entity_id)[:8],
                    "method": res.method,
                    "score": round(res.score, 3),
                    "queued": res.queued,
                }
            )
        queued = conn.execute(
            "SELECT provisional_entity_id AS a, candidate_entity_id AS b FROM er_candidates"
            " WHERE entity_type = %s",
            ("person" if kind == "people" else "company",),
        ).fetchall()

    queued_entities = {frozenset((q["a"], q["b"])) for q in queued}
    review = {
        frozenset((i, j))
        for i, j in combinations(predicted, 2)
        if frozenset((predicted[i], predicted[j])) in queued_entities
    }
    metrics = pairwise_clustering(predicted, gold, review)
    errors = []
    for i, j in combinations(predicted, 2):
        same_pred, same_gold = predicted[i] == predicted[j], gold[i] == gold[j]
        if same_pred and not same_gold:
            errors.append({"error": "false link", "a": _label(mentions[i]), "b": _label(mentions[j])})
        elif same_gold and not same_pred and frozenset((i, j)) not in review:
            errors.append({"error": "missed link", "a": _label(mentions[i]), "b": _label(mentions[j])})
    return {
        "metrics": metrics,
        "rows": rows,
        "errors": errors,
        "null_violations": null_violations,
    }


def run(**_: Any) -> SuiteResult:
    golden = load_yaml("er.yaml")
    people = _resolve_section("people", golden["people"], golden.get("team", []))
    companies = _resolve_section("companies", golden["companies"], [])

    metrics: dict[str, float] = {}
    for prefix, section in (("person", people), ("company", companies)):
        for k, v in section["metrics"].items():
            metrics[f"{prefix}_{k}"] = v
    # Combined pairwise precision over both entity types: the exit-gate metric.
    tp = sum(round(s["metrics"]["precision"] * s["metrics"]["predicted_pairs"]) for s in (people, companies))
    pred = sum(s["metrics"]["predicted_pairs"] for s in (people, companies))
    gold_pairs = sum(s["metrics"]["gold_pairs"] for s in (people, companies))
    metrics["precision"] = tp / pred if pred else 1.0
    metrics["recall"] = tp / gold_pairs if gold_pairs else 1.0
    metrics["free_mail_violations_ok"] = 1.0 if companies["null_violations"] == 0 else 0.0

    return SuiteResult(
        "entity_resolution",
        "deterministic",
        metrics,
        cases=[
            {"section": "people", "mentions": people["rows"], "errors": people["errors"]},
            {"section": "companies", "mentions": companies["rows"], "errors": companies["errors"]},
        ],
        model="local hash embeddings (no model call)",
    )
