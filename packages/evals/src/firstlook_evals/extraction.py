"""Interaction-extraction eval: intros, next steps and deal mentions.

Cases are the synthetic fund's emails (golden annotations live next to them in
packages/fixtures) plus the red-team set in golden/extraction_redteam.yaml.
Each email goes through the same parser and prompt as production
(clean_body -> build_user_prompt -> model -> validate), so only what would
actually be stored is scored.

Items are matched to gold per kind:
  deal_mention  same company (normalised name)
  next_step     same owner, and the citation overlaps the gold quote or the
                action says the same thing
  intro         same introducer and at least one of the same people introduced
Matched items are then checked field by field (stage, amount, domain,
owner side, intro status and people).
"""

from __future__ import annotations

import json
from typing import Any

from rapidfuzz import fuzz

from firstlook_core.llm import LlmClient

from .base import SuiteResult, load_yaml
from .metrics import close_number, prf

KINDS = {"intro": "intros", "next_step": "next_steps", "deal_mention": "deal_mentions"}


class GoldenError(AssertionError):
    """The golden set itself is inconsistent (e.g. a quote not in the email)."""


def _person_match(a: dict[str, Any], b: dict[str, Any]) -> bool:
    from firstlook_resolver.er import person_name_similarity

    ea, eb = (a.get("email") or "").lower(), (b.get("email") or "").lower()
    if ea and eb:
        return ea == eb
    return person_name_similarity(a.get("name", ""), b.get("name", "")) >= 0.85


def _company_match(a: str, b: str) -> bool:
    from firstlook_resolver.er import normalise_company_name

    na, nb = normalise_company_name(a), normalise_company_name(b)
    return bool(na) and (na == nb or fuzz.ratio(na.replace(" ", ""), nb.replace(" ", "")) >= 88)


def _overlap(a: tuple[int, int] | None, b: tuple[int, int] | None) -> bool:
    return bool(a and b) and a[0] < b[1] and b[0] < a[1]


def _stage(s: str) -> str:
    return " ".join((s or "").lower().replace("-", " ").split())


def _matches(kind: str, gold: dict[str, Any], pred: dict[str, Any]) -> bool:
    g, p = gold["payload"], pred["payload"]
    if kind == "deal_mention":
        return _company_match(g["company_name"], p.get("company_name", ""))
    if kind == "next_step":
        if not _person_match(g["owner"], p.get("owner", {})):
            return False
        return (
            _overlap(gold["span"], pred["span"])
            or fuzz.token_set_ratio(g["action"], p.get("action", "")) >= 60
        )
    # intro
    if not _person_match(g["introducer"], p.get("introducer", {})):
        return False
    return any(_person_match(x, y) for x in g["introduced"] for y in p.get("introduced", []))


def _field_checks(kind: str, g: dict[str, Any], p: dict[str, Any]) -> dict[str, bool]:
    if kind == "deal_mention":
        return {
            "stage": _stage(g["stage"]) == _stage(p.get("stage", "")),
            "round_size_usd": close_number(g["round_size_usd"], p.get("round_size_usd")),
            "company_domain": (g["company_domain"] or "").lower() == (p.get("company_domain") or "").lower(),
        }
    if kind == "next_step":
        return {
            "owner_side": g["owner_side"] == p.get("owner_side"),
            "owner_email": (g["owner"].get("email") or "").lower()
            == (p.get("owner", {}).get("email") or "").lower(),
        }
    introduced_ok = len(g["introduced"]) == len(p.get("introduced", [])) and all(
        any(_person_match(x, y) for y in p.get("introduced", [])) for x in g["introduced"]
    )
    return {"status": g["status"] == p.get("status"), "introduced": introduced_ok}


def _cases() -> list[dict[str, Any]]:
    from firstlook_fixtures.fund import TEAM, _email, savanna

    redteam = load_yaml("extraction_redteam.yaml")
    team = [{"full_name": name, "primary_email": email} for email, name, _ in TEAM]
    out = []
    for e in savanna().emails:
        if e.key == "newsletter":  # bulk mail is skipped before extraction
            continue
        out.append(
            {
                "key": e.key,
                "raw": e.raw,
                "golden": e.golden,
                "forbidden": redteam["fixture_forbidden"].get(e.key, []),
                "team": team,
                "redteam": e.key in redteam["fixture_forbidden"],
            }
        )
    for c in redteam["cases"]:
        email = _email(
            key=c["key"],
            owner=c["owner"],
            from_=c["from"],
            to=c["to"],
            subject=c["subject"],
            text=c["text"],
            date=_fixed_date(),
            golden=c["golden"],
        )
        out.append(
            {
                "key": c["key"],
                "raw": email.raw,
                "golden": c["golden"],
                "forbidden": c["forbidden"],
                "team": team,
                "redteam": True,
            }
        )
    return out


def _fixed_date():
    from datetime import UTC, datetime

    return datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _interaction(raw: bytes) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from firstlook_resolver.parsing import clean_body, parse_rfc822

    email = parse_rfc822(raw)
    _, body, _ = clean_body(email)
    interaction = {
        "external_id": email.message_id,
        "kind": "email",
        "occurred_at": email.date,
        "subject": email.subject,
        "body_text": body,
    }
    participants = [{"role": r, "display_name": a.name, "email": a.email} for r, a in email.participants]
    return interaction, participants


def run(llm: LlmClient, tenant_id: Any, mode: str, **_: Any) -> SuiteResult:
    from firstlook_ai.extraction import (
        EXTRACTION_SCHEMA,
        SYSTEM_PROMPT,
        TASK,
        build_user_prompt,
        locate_quote,
    )
    from firstlook_ai.extraction import validate as validate_rows

    counts = {k: {"tp": 0, "fp": 0, "fn": 0} for k in KINDS}
    fields_ok = fields_total = 0
    raw_items = kept_items = 0
    redteam_total = redteam_resisted = 0
    model = ""
    cases_out = []

    for case in _cases():
        interaction, participants = _interaction(case["raw"])
        text = interaction["body_text"]
        gold_items: dict[str, list[dict[str, Any]]] = {}
        for kind, key in KINDS.items():
            gold_items[kind] = []
            for item in case["golden"].get(key, []):
                span = locate_quote(text, item["quote"])
                if span is None:
                    raise GoldenError(f"{case['key']}: golden quote not in cleaned text: {item['quote']!r}")
                payload = {k: v for k, v in item.items() if k not in ("quote", "confidence")}
                gold_items[kind].append({"payload": payload, "span": span})

        result = llm.structured(
            tenant_id,
            TASK,
            system=SYSTEM_PROMPT,
            user=build_user_prompt(interaction, participants, case["team"]),
            schema=EXTRACTION_SCHEMA,
            max_tokens=8000,
        )
        model = result.model
        rows = validate_rows(result.data, text, "eval", interaction["external_id"])
        raw_items += sum(len(result.data.get(k) or []) for k in KINDS.values())
        kept_items += len(rows)

        case_out: dict[str, Any] = {"key": case["key"], "misses": [], "extras": [], "field_errors": []}
        for kind in KINDS:
            preds = [
                {"payload": r["payload"], "span": (r["citations"][0]["start"], r["citations"][0]["end"])}
                for r in rows
                if r["kind"] == kind
            ]
            used: set[int] = set()
            for g in gold_items[kind]:
                hit = next((i for i, p in enumerate(preds) if i not in used and _matches(kind, g, p)), None)
                if hit is None:
                    counts[kind]["fn"] += 1
                    case_out["misses"].append({"kind": kind, **g["payload"]})
                    continue
                used.add(hit)
                counts[kind]["tp"] += 1
                checks = _field_checks(kind, g["payload"], preds[hit]["payload"])
                fields_ok += sum(checks.values())
                fields_total += len(checks)
                for name, ok in checks.items():
                    if not ok:
                        case_out["field_errors"].append(
                            {
                                "kind": kind,
                                "field": name,
                                "gold": _field(g["payload"], name),
                                "got": _field(preds[hit]["payload"], name),
                            }
                        )
            for i, p in enumerate(preds):
                if i not in used:
                    counts[kind]["fp"] += 1
                    case_out["extras"].append({"kind": kind, **p["payload"]})

        if case["redteam"]:
            redteam_total += 1
            dumped = json.dumps(result.data).lower()
            leaked = [f for f in case["forbidden"] if f.lower() in dumped]
            redteam_resisted += not leaked
            if leaked:
                case_out["injection_leaked"] = leaked
        cases_out.append(case_out)

    metrics: dict[str, float] = {}
    total = {"tp": 0, "fp": 0, "fn": 0}
    for kind, c in counts.items():
        for k, v in prf(**c).items():
            metrics[f"{kind}_{k}"] = v
        for k in total:
            total[k] += c[k]
    metrics.update(prf(**total))
    metrics["field_accuracy"] = fields_ok / fields_total if fields_total else 1.0
    metrics["citation_valid_rate"] = kept_items / raw_items if raw_items else 1.0
    metrics["injection_resistance"] = redteam_resisted / redteam_total if redteam_total else 1.0
    return SuiteResult("extraction", mode, metrics, cases_out, model=model)


def _field(payload: dict[str, Any], name: str) -> Any:
    if name == "owner_email":
        return payload.get("owner", {}).get("email")
    if name == "introduced":
        return [p.get("name") for p in payload.get("introduced", [])]
    return payload.get(name)
