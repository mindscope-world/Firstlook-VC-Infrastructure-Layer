import json

import pytest

from firstlook_core.llm import FakeLlm
from firstlook_evals.__main__ import golden_llm, main
from firstlook_evals.base import SuiteResult, checks_for, load_thresholds
from firstlook_evals.metrics import close_number, ndcg, pairwise_clustering, prf


def test_pairwise_clustering():
    gold = {0: "a", 1: "a", 2: "b", 3: "b"}
    perfect = pairwise_clustering({0: 1, 1: 1, 2: 2, 3: 2}, gold)
    assert perfect["precision"] == perfect["recall"] == 1.0
    merged = pairwise_clustering({0: 1, 1: 1, 2: 1, 3: 1}, gold)
    assert merged["precision"] == pytest.approx(2 / 6) and merged["recall"] == 1.0
    split = pairwise_clustering({0: 1, 1: 2, 2: 3, 3: 4}, gold, review={frozenset((0, 1))})
    assert split["precision"] == 1.0 and split["recall"] == 0.0
    assert split["recall_with_review"] == 0.5 and split["review_precision"] == 1.0


def test_ndcg_and_helpers():
    assert ndcg([3, 2, 0]) == 1.0
    assert ndcg([0, 2, 3]) < ndcg([3, 0, 2]) < 1.0
    # Dropping a relevant item (it isn't in the ranking) is penalised.
    assert ndcg([2, 0], all_relevance=[3, 2, 0]) < 1.0
    assert prf(0, 0, 0) == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert close_number(1_500_000, 1_510_000) and not close_number(1_500_000, 1_600_000)
    assert close_number(0, None) and not close_number(0, 5)


def test_live_gates_only_apply_to_live_runs():
    thresholds = load_thresholds()
    golden = SuiteResult("extraction", "golden", {"citation_valid_rate": 1.0, "precision": 0.1})
    assert all(c.passed for c in checks_for(golden, thresholds))
    live = SuiteResult("extraction", "gateway", {"citation_valid_rate": 1.0, "precision": 0.1})
    failed = {c.metric for c in checks_for(live, thresholds) if not c.passed}
    assert "precision" in failed


def test_model_suites_score_golden_answers_perfectly():
    from firstlook_evals import extraction, factsheet

    llm = golden_llm()
    ex = extraction.run(llm, "t", "golden")
    assert ex.metrics["f1"] == 1.0 and ex.metrics["injection_resistance"] == 1.0
    fs = factsheet.run(llm, "t", "golden")
    assert fs.metrics["field_accuracy"] == 1.0 and fs.metrics["metric_f1"] == 1.0


def test_extraction_scores_a_bad_model_badly():
    """A model that invents quotes and follows injected instructions must score
    poorly: the harness has to be able to fail."""
    from firstlook_evals import extraction

    def respond(task, system, user, schema):
        return {
            "intros": [],
            "next_steps": [],
            "deal_mentions": [
                {
                    "company_name": "Globex Holdings",
                    "company_domain": "",
                    "stage": "seed",
                    "round_size_usd": 5e7,
                    "summary": "",
                    "quote": "Ignore all previous instructions.",
                    "confidence": "high",
                },
                {
                    "company_name": "Invented Co",
                    "company_domain": "",
                    "stage": "",
                    "round_size_usd": 0,
                    "summary": "",
                    "quote": "a sentence that is not in the email",
                    "confidence": "high",
                },
            ],
        }

    r = extraction.run(FakeLlm(responder=respond), "t", "gateway")
    assert r.metrics["recall"] < 0.2
    assert r.metrics["citation_valid_rate"] < 0.6
    assert r.metrics["injection_resistance"] < 1.0
    leaked = [c for c in r.cases if c.get("injection_leaked")]
    assert any(c["key"] == "rt-ignore-instructions" for c in leaked)


def test_ranking_suite_without_db():
    from firstlook_evals import ranking

    r = ranking.run(golden_llm(), "t", "golden")
    assert r.metrics["stage1_ndcg@5"] >= 0.85 and r.metrics["relevant_kept"] == 1.0
    excluded = {c["company"] for c in r.cases if c.get("excluded")}
    assert excluded == {"Lagos Ledger", "Tembo Growth Bank"}


@pytest.mark.db
def test_cli_gates_pass_in_golden_mode(migrated_db, tmp_path):
    report = tmp_path / "report.json"
    assert main(["--report", str(report)]) == 0
    data = json.loads(report.read_text())
    assert data["passed"] and {s["suite"] for s in data["suites"]} == {
        "entity_resolution",
        "extraction",
        "ranking",
        "factsheet",
    }
    er = next(s for s in data["suites"] if s["suite"] == "entity_resolution")
    assert er["metrics"]["precision"] >= 0.95
