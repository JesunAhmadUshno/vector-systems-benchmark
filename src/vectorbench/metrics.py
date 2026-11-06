"""Metric definitions for the benchmark.

Every formula here is the one named in SPEC.md. Tests pin these definitions
on small examples with known answers.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np


def recall_at_k(returned: Sequence[Sequence[int]], ground_truth: Sequence[Sequence[int]], k: int) -> float:
    """Mean over queries of |returned top-k intersect exact top-k| / k."""
    if len(returned) != len(ground_truth):
        raise ValueError("returned and ground_truth must have the same number of queries")
    if not returned:
        return 0.0
    total = 0.0
    for ret, gt in zip(returned, ground_truth):
        gt_set = set(list(gt)[:k])
        ret_set = set(list(ret)[:k])
        total += len(gt_set & ret_set) / k
    return total / len(returned)


def shortfall_rate(returned: Sequence[Sequence[int]], k: int) -> float:
    """Share of queries that returned fewer than k results.

    This is the user-visible form of overfiltering: the caller asked for k
    results and silently got fewer.
    """
    if not returned:
        return 0.0
    short = sum(1 for ret in returned if len(ret) < k)
    return short / len(returned)


def mean_returned(returned: Sequence[Sequence[int]]) -> float:
    """Mean number of results returned per query."""
    if not returned:
        return 0.0
    return float(np.mean([len(ret) for ret in returned]))


def stale_rate(returned: Sequence[Sequence[int]], deleted_ids: Iterable[int]) -> float:
    """Share of all returned slots that hold a deleted id."""
    deleted = set(deleted_ids)
    total = 0
    stale = 0
    for ret in returned:
        for rid in ret:
            total += 1
            if rid in deleted:
                stale += 1
    if total == 0:
        return 0.0
    return stale / total


def percentiles_ms(latencies_ms: Sequence[float]) -> dict:
    """p50 and p95 of per-query latency in milliseconds (linear interpolation)."""
    arr = np.asarray(latencies_ms, dtype=np.float64)
    if arr.size == 0:
        return {"p50": 0.0, "p95": 0.0}
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
    }


def ndcg_at_k(ranked: Sequence[int], relevant: set[int], k: int) -> float:
    """nDCG at k with binary relevance.

    DCG = sum over ranks i (0-based) of rel_i / log2(i + 2). IDCG is the DCG
    of the ideal ranking, which places min(|relevant|, k) relevant items
    first.
    """
    dcg = 0.0
    for i, rid in enumerate(list(ranked)[:k]):
        if rid in relevant:
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def recall_at_depth(ranked: Sequence[int], relevant: set[int], depth: int) -> float:
    """Share of all relevant items found in the top `depth` results."""
    if not relevant:
        return 0.0
    found = sum(1 for rid in list(ranked)[:depth] if rid in relevant)
    return found / len(relevant)


def rrf_fuse(rankings: Sequence[Sequence[int]], k_const: int = 60, depth: int | None = None) -> list[int]:
    """Reciprocal rank fusion over several rankings of ids.

    Score of an id is the sum over rankings of 1 / (k_const + rank), with
    rank starting at 1. Returns ids ordered by score, ties broken by the
    best (smallest) rank seen, then by id for determinism.
    """
    scores: dict[int, float] = {}
    best_rank: dict[int, int] = {}
    for ranking in rankings:
        items = list(ranking) if depth is None else list(ranking)[:depth]
        for rank, rid in enumerate(items, start=1):
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k_const + rank)
            if rid not in best_rank or rank < best_rank[rid]:
                best_rank[rid] = rank
    ordered = sorted(scores.keys(), key=lambda rid: (-scores[rid], best_rank[rid], rid))
    return ordered
