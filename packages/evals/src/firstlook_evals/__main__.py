"""Run the eval suites and gate on thresholds.yaml.

    uv run python -m firstlook_evals                    # all suites, golden answers (no model calls)
    uv run python -m firstlook_evals --llm gateway      # live model through the LLM gateway
    uv run python -m firstlook_evals er ranking -v      # some suites, with per-case detail

Modes:
  golden   The LLM is replaced by the golden answers. Scores the deterministic
           parts for real (entity resolution, stage-1 ranking, quote
           validation) and checks the harness and golden sets are consistent.
  gateway  Real model calls through services/gateway (needs the gateway
           running with ANTHROPIC_API_KEY). Also applies the `live`
           thresholds that measure model quality.

Exit status is 1 if any applicable threshold fails. A JSON report is written
to packages/evals/reports/<mode>-latest.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from firstlook_core.llm import FakeLlm, GatewayClient, LlmClient

from .base import PACKAGE_ROOT, Check, SuiteResult, checks_for, eval_tenant, load_thresholds

SUITES = ["er", "extraction", "ranking", "factsheet"]
_ID = re.compile(r'<interaction id="<([^@>]+)@fixtures\.firstlook\.local>"')


def golden_llm() -> FakeLlm:
    """Answers every structured call with the golden annotation for that case."""
    from firstlook_fixtures.fund import savanna
    from firstlook_fixtures.seed import fixture_rerank

    from .base import load_yaml
    from .factsheet import golden_answer as factsheet_answer

    golden = {e.key: e.golden for e in savanna().emails}
    golden.update({c["key"]: c["golden"] for c in load_yaml("extraction_redteam.yaml")["cases"]})

    def respond(task: str, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        if task == "sourcing.rerank":
            return fixture_rerank(user)
        if task.startswith("extract.factsheet"):
            return factsheet_answer(user)
        m = _ID.search(user)
        return golden.get(m.group(1), {}) if m else {"intros": [], "next_steps": [], "deal_mentions": []}

    return FakeLlm(responder=respond, model="golden (no model call)")


def run_suite(name: str, llm: LlmClient, tenant_id: Any, mode: str) -> SuiteResult:
    if name == "er":
        from . import er

        return er.run()
    if name == "extraction":
        from . import extraction

        return extraction.run(llm, tenant_id, mode)
    if name == "ranking":
        from . import ranking

        return ranking.run(llm, tenant_id, mode)
    if name == "factsheet":
        from . import factsheet

        return factsheet.run(llm, tenant_id, mode)
    raise ValueError(name)


def _print(result: SuiteResult, checks: list[Check], verbose: bool) -> None:
    gates = {c.metric: c for c in checks}
    print(f"\n{result.suite}  [{result.mode}; {result.model or 'no model'}]")
    for metric, value in result.metrics.items():
        if metric.endswith(("_pairs",)) and not verbose:
            continue
        gate = gates.get(metric)
        mark = "" if gate is None else ("  ok  " if gate.passed else "  FAIL") + f" (min {gate.minimum:g})"
        print(f"  {metric:<32} {value:8.3f}{mark}")
    for n in result.notes:
        print(f"  note: {n}")
    if verbose:
        for case in result.cases:
            interesting = {k: v for k, v in case.items() if v not in ([], None, "")}
            print("   ", json.dumps(interesting, default=str, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firstlook-evals")
    parser.add_argument("suites", nargs="*", help=f"any of {SUITES} (default: all)")
    parser.add_argument("--llm", choices=["golden", "gateway"], default="golden")
    parser.add_argument("-v", "--verbose", action="store_true", help="print per-case results")
    parser.add_argument("--report", help="where to write the JSON report")
    args = parser.parse_args(argv)
    suites = args.suites or SUITES
    if unknown := [s for s in suites if s not in SUITES]:
        parser.error(f"unknown suite(s) {unknown}; choose from {SUITES}")

    if args.llm == "gateway":
        llm: LlmClient = GatewayClient()
        tenant_id: Any = eval_tenant()
    else:
        llm, tenant_id = golden_llm(), "00000000-0000-0000-0000-00000000e7a1"

    thresholds = load_thresholds()
    results, all_checks = [], []
    for name in suites:
        result = run_suite(name, llm, tenant_id, args.llm)
        if args.llm == "gateway" and result.model == "offline":
            print(
                "The gateway answered with its offline stand-in (no ANTHROPIC_API_KEY), so live scores"
                " would be meaningless. Set the key for the gateway and retry.",
                file=sys.stderr,
            )
            return 2
        checks = checks_for(result, thresholds)
        _print(result, checks, args.verbose)
        results.append(result)
        all_checks += checks

    failed = [c for c in all_checks if not c.passed]
    report = {
        "mode": args.llm,
        "at": datetime.now(UTC).isoformat(),
        "passed": not failed,
        "suites": [asdict(r) for r in results],
        "checks": [{**asdict(c), "passed": c.passed} for c in all_checks],
    }
    path = args.report or PACKAGE_ROOT / "reports" / f"{args.llm}-latest.json"
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, default=str))

    print(f"\nReport: {path}")
    if failed:
        print(f"{len(failed)} threshold(s) failed:")
        for c in failed:
            print(
                f"  {c.suite}.{c.metric} = {c.value if c.value is None else round(c.value, 3)} < {c.minimum}"
            )
        return 1
    print(f"All {len(all_checks)} thresholds passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
