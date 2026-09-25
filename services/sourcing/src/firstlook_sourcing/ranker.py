"""Stage 1 ranking: features, hard filters, and a scoring model.

Features are all in [0, 1] so they are comparable and explainable in the UI.

    sector    thesis sectors overlap the company's
    stage     same stage 1.0, adjacent 0.5 (two or more away is filtered out)
    geo       company country inside the thesis geographies
    cheque    the thesis cheque range overlaps a typical participation (5–35%)
              of the company's last or stage-typical round
    text      similarity of the company description to the thesis description
    momentum  funding recency, hiring, GitHub activity and news mentions
    warm      strongest team relationship with anyone at the company

Cold start uses fixed weights (RulesRanker). Once a thesis has enough thumbs
up/down, a logistic model is fitted on the same features (LogisticRanker).
The plan's XGBoost ranker replaces it at ~500 labels per fund; the Ranker
protocol is the seam for that.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from firstlook_core.embeddings import cosine

from .taxonomy import STAGES, expand_geographies, stage_distance

FEATURES = ["sector", "stage", "geo", "cheque", "text", "momentum", "warm"]
RULE_WEIGHTS = {
    "sector": 0.22,
    "stage": 0.14,
    "geo": 0.12,
    "cheque": 0.08,
    "text": 0.18,
    "momentum": 0.16,
    "warm": 0.10,
}
TYPICAL_ROUND_USD = {
    "pre-seed": 5e5,
    "seed": 2e6,
    "series-a": 8e6,
    "series-b": 25e6,
    "series-c": 60e6,
    "growth": 120e6,
}
MIN_LABELS_FOR_LEARNED = 30

_WORD = re.compile(r"[a-z][a-z\-]{3,}")
_STOP = {
    "with",
    "that",
    "from",
    "their",
    "this",
    "which",
    "into",
    "across",
    "about",
    "companies",
    "company",
    "startups",
    "startup",
    "build",
    "building",
    "using",
    "based",
    "first",
    "more",
    "than",
    "they",
    "have",
}


@dataclass
class Candidate:
    company: dict[str, Any]  # companies row (+ vector as list)
    signals: dict[str, Any]  # aggregated signals
    warm: float  # strongest knows edge to anyone at the company


@dataclass
class Scored:
    company_id: Any
    score: float
    features: dict[str, float]
    excluded: str | None = None  # reason, when a hard filter removed it


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def cheque_fit(thesis_min: float | None, thesis_max: float | None, round_usd: float | None) -> float:
    if not round_usd or (thesis_min is None and thesis_max is None):
        return 0.5
    lo, hi = 0.05 * round_usd, 0.35 * round_usd
    tmin, tmax = thesis_min or 0.0, thesis_max or float("inf")
    if tmin <= hi and tmax >= lo:
        return 1.0
    gap = (tmin / hi) if tmin > hi else (lo / tmax)
    return max(0.0, 1.0 - math.log10(gap) / 0.75)  # 2x off -> 0.6, 3x -> 0.36, ~6x or more -> 0


def momentum(signals: dict[str, Any], last_round_at: date | None, today: date | None = None) -> float:
    today = today or datetime.now(UTC).date()
    parts: list[float] = []
    if last_round_at:
        months = (today - last_round_at).days / 30.4
        parts.append(1.0 if months < 6 else 0.6 if months < 12 else 0.3 if months < 24 else 0.1)
    else:
        parts.append(0.3)
    roles, roles_before = signals.get("open_roles"), signals.get("open_roles_30d_ago")
    if roles is not None:
        growth = (roles - roles_before) / max(roles_before, 1) if roles_before is not None else 0.0
        parts.append(min(1.0, 0.4 + 0.1 * roles + max(0.0, growth)))
    if signals.get("github_active_repos_30d") is not None:
        parts.append(min(1.0, math.log1p(signals["github_active_repos_30d"]) / math.log1p(10)))
    parts.append(min(1.0, math.log1p(signals.get("news_mentions_90d", 0)) / math.log1p(5)))
    return sum(parts) / len(parts)


def features(c: Candidate, thesis: dict[str, Any], today: date | None = None) -> Scored:
    co = c.company
    f: dict[str, float] = {}

    t_sectors = set(thesis["sectors"])
    f["sector"] = 0.5 if not t_sectors else (1.0 if t_sectors & set(co["sectors"] or []) else 0.0)

    if not thesis["stages"]:
        f["stage"] = 0.5
    elif not co["stage"]:
        f["stage"] = 0.4
    else:
        d = min((stage_distance(co["stage"], s) for s in thesis["stages"] if s in STAGES), default=None)
        if d is not None and d >= 2:
            return Scored(co["id"], 0.0, f, excluded=f"stage {co['stage']}")
        f["stage"] = 1.0 if d == 0 else 0.5

    countries = expand_geographies(thesis["geographies"])
    if not countries:
        f["geo"] = 0.5
    elif not co["country"]:
        f["geo"] = 0.4
    elif co["country"] in countries:
        f["geo"] = 1.0
    else:
        return Scored(co["id"], 0.0, f, excluded=f"geography {co['country']}")

    round_usd = co["last_round_usd"] or TYPICAL_ROUND_USD.get(co["stage"] or "")
    f["cheque"] = cheque_fit(
        thesis["cheque_min_usd"], thesis["cheque_max_usd"], float(round_usd) if round_usd else None
    )

    text = 0.0
    if co.get("description_vec") and thesis.get("embedding_vec"):
        text = max(0.0, cosine(co["description_vec"], thesis["embedding_vec"]))
    if co["description"] and thesis["description"]:
        tk, ck = _keywords(thesis["description"]), _keywords(co["description"])
        if tk:
            text = max(text, min(1.0, 2.5 * len(tk & ck) / len(tk)))
    f["text"] = round(text, 4)

    f["momentum"] = round(momentum(c.signals, co["last_round_at"], today), 4)
    f["warm"] = round(min(1.0, c.warm), 4)
    return Scored(co["id"], 0.0, f)


class Ranker(Protocol):
    name: str

    def score(self, f: dict[str, float]) -> float: ...


class RulesRanker:
    name = "rules-v1"

    def score(self, f: dict[str, float]) -> float:
        return sum(RULE_WEIGHTS[k] * f.get(k, 0.0) for k in FEATURES) / sum(RULE_WEIGHTS.values())


@dataclass
class LogisticRanker:
    weights: dict[str, float]
    bias: float
    model_id: str = "unsaved"

    @property
    def name(self) -> str:
        return f"learned:{self.model_id}"

    def score(self, f: dict[str, float]) -> float:
        z = self.bias + sum(self.weights[k] * f.get(k, 0.0) for k in FEATURES)
        return 1 / (1 + math.exp(-z))


def train_logistic(
    rows: list[tuple[dict[str, float], int]],
    epochs: int = 400,
    lr: float = 0.5,
    l2: float = 0.01,
    seed: int = 7,
) -> tuple[LogisticRanker, dict[str, float]]:
    """Fit on (features, vote) pairs, vote in {-1, 1}. Returns the model and
    holdout accuracy (20% split). Small and dependency-free on purpose."""
    data = [(f, 1 if v > 0 else 0) for f, v in rows]
    rnd = random.Random(seed)
    rnd.shuffle(data)
    cut = max(1, len(data) // 5)
    test, train = data[:cut], data[cut:] or data
    w = {k: 0.0 for k in FEATURES}
    b = 0.0
    for _ in range(epochs):
        gw = {k: 0.0 for k in FEATURES}
        gb = 0.0
        for f, y in train:
            p = 1 / (1 + math.exp(-(b + sum(w[k] * f.get(k, 0.0) for k in FEATURES))))
            for k in FEATURES:
                gw[k] += (p - y) * f.get(k, 0.0)
            gb += p - y
        n = len(train)
        for k in FEATURES:
            w[k] -= lr * (gw[k] / n + l2 * w[k])
        b -= lr * gb / n
    model = LogisticRanker(w, b)
    correct = sum(1 for f, y in test if (model.score(f) >= 0.5) == (y == 1))
    return model, {"holdout_accuracy": round(correct / len(test), 3), "train": len(train), "test": len(test)}
