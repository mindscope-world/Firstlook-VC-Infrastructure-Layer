from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import respx

from firstlook_core.llm import FakeLlm
from firstlook_sourcing.ranker import (
    FEATURES,
    Candidate,
    RulesRanker,
    cheque_fit,
    features,
    momentum,
    train_logistic,
)
from firstlook_sourcing.rerank import CandidateFacts, Fact, rerank
from firstlook_sourcing.sources.github import GitHubSource
from firstlook_sourcing.sources.jobs import JobBoardSource
from firstlook_sourcing.sources.news import NewsSource, parse_amount, parse_feed
from firstlook_sourcing.sources.registry import parse_registry_csv
from firstlook_sourcing.sources.vendor import SandboxVendor, VendorQuery
from firstlook_sourcing.taxonomy import (
    expand_geographies,
    normalise_country,
    normalise_sectors,
    normalise_stage,
)

DATA = Path(__file__).resolve().parents[3] / "packages" / "fixtures" / "data"
THESIS = {
    "sectors": ["fintech", "agritech"],
    "stages": ["pre-seed", "seed"],
    "geographies": ["east-africa"],
    "cheque_min_usd": 250_000.0,
    "cheque_max_usd": 1_000_000.0,
    "embedding_vec": None,
    "description": "Credit and payments infrastructure for smallholder farmers and informal merchants",
}


def test_taxonomy():
    assert normalise_sectors(["Fin-Tech", "Payments", "AgTech", "Unknown"]) == ["fintech", "agritech"]
    assert normalise_stage("Series A") == "series-a" and normalise_stage("Seed Extension") == "seed"
    assert normalise_stage("Pre-Seed round") == "pre-seed" and normalise_stage("weird") is None
    assert normalise_country("Kenya") == "KE" and normalise_country("ng") == "NG"
    assert {"KE", "UG", "TZ", "RW"} <= expand_geographies(["east-africa"])
    assert expand_geographies(["Nigeria", "GH"]) == {"NG", "GH"}


def test_sandbox_vendor_filters():
    v = SandboxVendor(DATA / "vendor_sandbox.json")
    hits = v.search(VendorQuery(["fintech", "agritech"], ["pre-seed", "seed"], ["east-africa"]))
    names = {h.profile.name for h in hits}
    assert {"Chama Pay", "Mavuno Credit", "Kilimo Data"} <= names
    assert not names & {"NairaStack", "Cairo Carts", "Lipa Later Kenya", "Elimu Plus"}
    kilimo = v.lookup("kilimodata.co.ke")
    assert kilimo.profile.stage == "pre-seed" and kilimo.profile.country == "KE"
    assert kilimo.profile.last_round_at == date(2025, 8, 12)
    assert any(o.signal == "funding_round_usd" and o.value == 400000 for o in kilimo.observations)


def test_news_parsing_and_funding_detection():
    items = parse_feed((DATA / "news_feed.xml").read_text(), "https://news.example/feed")
    assert len(items) == 5
    found = {p.name: (p.last_round_usd, p.stage) for p, _ in NewsSource.funding_announcements(items)}
    assert found["Chama Pay"] == (350000, "pre-seed")
    assert found["Mavuno Credit"] == (1_200_000, "seed")
    assert found["Nyuki Labs"] == (600_000, "seed")
    assert not any(n.startswith("The") for n in found)
    mentions = NewsSource.mentions(items, {"k1": "Kilimo Data", "x": "Pay"})
    assert [o.url for o in mentions["k1"]] == ["https://news.example/kilimo-lenders"]
    assert "x" not in mentions  # names under 4 characters are too ambiguous
    assert parse_amount("$1.5M") == 1_500_000 and parse_amount("$600K") == 600_000


def test_registry_extract():
    rows = parse_registry_csv((DATA / "ke_brs_extract.csv").read_text())
    names = [p.name for p, _ in rows]
    assert "Old Traders Limited" not in names  # dissolved
    mkulima = next(p for p, _ in rows if p.name.startswith("Mkulima"))
    assert mkulima.registry_id == "ke-brs:PVT-AB12CD34" and mkulima.country == "KE"
    assert {"fintech", "agritech"} <= set(mkulima.sectors)


@respx.mock
def test_github_and_job_boards():
    respx.get("https://api.github.com/orgs/acme/repos").respond(
        json=[
            {
                "name": "api",
                "stargazers_count": 40,
                "pushed_at": datetime.now(UTC).isoformat(),
                "fork": False,
            },
            {"name": "old", "stargazers_count": 5, "pushed_at": "2020-01-01T00:00:00Z", "fork": False},
            {
                "name": "fork",
                "stargazers_count": 999,
                "pushed_at": datetime.now(UTC).isoformat(),
                "fork": True,
            },
        ]
    )
    obs = {o.signal: o.value for o in GitHubSource(http=httpx.Client()).observe("acme")}
    assert obs == {"github_stars": 45, "github_public_repos": 2, "github_active_repos_30d": 1}

    respx.get("https://boards-api.greenhouse.io/v1/boards/acme/jobs").respond(
        json={"jobs": [{"title": "Senior Backend Engineer"}, {"title": "Sales Lead"}]}
    )
    respx.get("https://api.lever.co/v0/postings/gone").respond(404)
    jobs = JobBoardSource(http=httpx.Client())
    assert {o.signal: o.value for o in jobs.observe("greenhouse:acme")} == {
        "open_roles": 2,
        "open_engineering_roles": 1,
    }
    assert jobs.observe("lever:gone") == []


def _cand(**over):
    company = {
        "id": "c",
        "sectors": ["fintech"],
        "stage": "seed",
        "country": "KE",
        "last_round_usd": 1_500_000.0,
        "last_round_at": date(2026, 6, 1),
        "description": "Payments for informal merchants and farmers",
        "description_vec": None,
    } | over
    return Candidate(company, {"open_roles": 4, "news_mentions_90d": 1}, 0.6)


def test_features_and_hard_filters():
    today = date(2026, 9, 25)
    s = features(_cand(), THESIS, today)
    assert s.excluded is None
    assert s.features["sector"] == 1 and s.features["stage"] == 1 and s.features["geo"] == 1
    assert s.features["cheque"] == 1 and s.features["text"] > 0.3 and s.features["warm"] == 0.6
    assert features(_cand(country="NG"), THESIS, today).excluded == "geography NG"
    assert features(_cand(stage="series-b"), THESIS, today).excluded == "stage series-b"
    assert features(_cand(stage="series-a"), THESIS, today).features["stage"] == 0.5
    assert features(_cand(country=None), THESIS, today).features["geo"] == 0.4
    off = features(_cand(sectors=["edtech"]), THESIS, today)
    assert RulesRanker().score(off.features) < RulesRanker().score(s.features)


def test_cheque_fit_and_momentum():
    assert cheque_fit(250_000, 1_000_000, 2_000_000) == 1.0  # 5-35% of $2M overlaps
    assert cheque_fit(250_000, 1_000_000, 60_000_000) < 0.5  # far too big a round
    assert cheque_fit(None, None, 1_000_000) == 0.5
    fresh = momentum(
        {"open_roles": 6, "open_roles_30d_ago": 2, "news_mentions_90d": 3},
        date(2026, 8, 1),
        date(2026, 9, 25),
    )
    stale = momentum({"news_mentions_90d": 0}, date(2023, 1, 1), date(2026, 9, 25))
    assert fresh > 0.7 > stale


def test_learned_ranker_learns_preference():
    good = {k: 0.5 for k in FEATURES} | {"warm": 0.9, "momentum": 0.8}
    bad = {k: 0.5 for k in FEATURES} | {"warm": 0.1, "momentum": 0.2}
    rows = [(good, 1)] * 25 + [(bad, -1)] * 25
    model, metrics = train_logistic(rows)
    assert model.score(good) > 0.7 > 0.3 > model.score(bad)
    assert metrics["holdout_accuracy"] == 1.0


def test_rerank_keeps_only_valid_citations():
    cands = [
        CandidateFacts(
            "c1",
            "id-1",
            "Chama Pay",
            [
                Fact("c1.f1", "Profile: fintech", "profile"),
                Fact("c1.f2", "Raised $350,000", "signal", "https://x"),
            ],
        ),
        CandidateFacts("c2", "id-2", "Tamu Foods", [Fact("c2.f1", "Profile: food", "profile")]),
    ]

    def respond(task, system, user, schema):
        assert "<facts>" in user and "treat it as data" in system.lower()
        return {
            "rankings": [
                {
                    "company_key": "c1",
                    "fit": 82,
                    "rationale": "Fintech at pre-seed.",
                    "concerns": "",
                    "evidence": ["c1.f2", "c1.f9", "c2.f1"],
                },
                {"company_key": "c9", "fit": 99, "rationale": "Invented.", "concerns": "", "evidence": []},
                {
                    "company_key": "c2",
                    "fit": 150,
                    "rationale": "Not a fit.",
                    "concerns": "Consumer food.",
                    "evidence": [],
                },
            ]
        }

    out, model = rerank(FakeLlm(respond), "t", THESIS | {"name": "T", "founder_profile": ""}, cands)
    by = {r.company_id: r for r in out}
    assert set(by) == {"id-1", "id-2"}
    assert [c["fact_id"] for c in by["id-1"].citations] == ["c1.f2"]
    assert by["id-1"].citations[0]["url"] == "https://x"
    assert by["id-1"].stage2 == 0.82 and by["id-2"].stage2 == 1.0
