"""Scoring primitives shared by the suites."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from itertools import combinations


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    """Precision, recall and F1. Empty predictions against empty gold score 1."""
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def linked_pairs(assignment: dict[int, Hashable]) -> set[frozenset[int]]:
    """All unordered pairs of mentions assigned to the same cluster."""
    clusters: dict[Hashable, list[int]] = {}
    for mention, cluster in assignment.items():
        clusters.setdefault(cluster, []).append(mention)
    return {frozenset(p) for members in clusters.values() for p in combinations(sorted(members), 2)}


def pairwise_clustering(
    predicted: dict[int, Hashable],
    gold: dict[int, Hashable],
    review: set[frozenset[int]] | None = None,
) -> dict[str, float]:
    """Pairwise precision/recall of a clustering against gold clusters.

    `review` holds mention pairs the system did not link but queued for a
    human to decide. They don't count as links for precision; they are scored
    separately (how much recall the queue recovers, and how often a queued
    pair really is the same entity).
    """
    pred, true = linked_pairs(predicted), linked_pairs(gold)
    review = (review or set()) - pred
    tp = len(pred & true)
    out = prf(tp, len(pred - true), len(true - pred))
    out["recall_with_review"] = len((pred | review) & true) / len(true) if true else 1.0
    out["review_precision"] = len(review & true) / len(review) if review else 1.0
    out["predicted_pairs"] = len(pred)
    out["gold_pairs"] = len(true)
    out["review_pairs"] = len(review)
    return out


def dcg(gains: Iterable[float]) -> float:
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg(
    ranked_relevance: list[float], all_relevance: list[float] | None = None, k: int | None = None
) -> float:
    """NDCG@k of a ranking given each ranked item's graded relevance.

    all_relevance is the relevance of every item that could have been ranked
    (including any the system dropped), so the ideal ordering is computed over
    the full pool and dropping a relevant item is penalised.
    """
    pool = sorted(all_relevance if all_relevance is not None else ranked_relevance, reverse=True)
    k = k or len(pool)
    ideal = dcg(pool[:k])
    return dcg(ranked_relevance[:k]) / ideal if ideal else 1.0


def close_number(a: float | None, b: float | None, rel: float = 0.02) -> bool:
    """Numbers agree within a relative tolerance; 0/None both mean unknown."""
    a, b = a or 0.0, b or 0.0
    if a == 0 or b == 0:
        return a == b
    return abs(a - b) <= rel * max(abs(a), abs(b))
