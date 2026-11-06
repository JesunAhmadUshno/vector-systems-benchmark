import math

import numpy as np
import pytest

from vectorbench.metrics import (
    mean_returned,
    ndcg_at_k,
    percentiles_ms,
    recall_at_depth,
    recall_at_k,
    rrf_fuse,
    shortfall_rate,
    stale_rate,
)


def test_recall_at_k_perfect_and_zero():
    gt = [[1, 2, 3], [4, 5, 6]]
    assert recall_at_k(gt, gt, 3) == 1.0
    assert recall_at_k([[9, 8, 7], [6, 5, 4]], gt, 3) == pytest.approx(0.5)


def test_recall_at_k_uses_top_k_only():
    gt = [[1, 2, 3, 4]]
    ret = [[1, 2, 99, 3]]
    # At k=3 the returned top 3 are {1, 2, 99}; the exact top 3 are {1, 2, 3}.
    assert recall_at_k(ret, gt, 3) == pytest.approx(2 / 3)


def test_shortfall_and_mean_returned():
    ret = [[1, 2], [1, 2, 3, 4]]
    assert shortfall_rate(ret, 4) == 0.5
    assert mean_returned(ret) == 3.0


def test_stale_rate():
    ret = [[1, 2, 3], [4, 5, 6]]
    assert stale_rate(ret, {2, 5}) == pytest.approx(2 / 6)
    assert stale_rate(ret, set()) == 0.0


def test_percentiles():
    p = percentiles_ms([10.0, 20.0, 30.0, 40.0])
    assert p["p50"] == pytest.approx(25.0)
    assert p["p95"] == pytest.approx(38.5)


def test_ndcg_known_values():
    relevant = {1, 2}
    # Ideal order: nDCG 1.
    assert ndcg_at_k([1, 2, 3], relevant, 3) == pytest.approx(1.0)
    # Relevant items at ranks 2 and 3 (0-based 1 and 2).
    dcg = 1 / math.log2(3) + 1 / math.log2(4)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert ndcg_at_k([9, 1, 2], relevant, 3) == pytest.approx(dcg / idcg)
    # No relevant items shown.
    assert ndcg_at_k([9, 8, 7], relevant, 3) == 0.0


def test_recall_at_depth():
    assert recall_at_depth([1, 9, 2, 9], {1, 2, 3}, 4) == pytest.approx(2 / 3)
    assert recall_at_depth([1], {1, 2, 3}, 4) == pytest.approx(1 / 3)


def test_rrf_fuse_order_and_determinism():
    fused = rrf_fuse([[1, 2, 3], [3, 2, 1]], k_const=60)
    # Doc 2 and 3 tie on score by symmetry of the two rankings; doc 2 has
    # ranks (2, 2) and doc 3 has ranks (3, 1), so doc 3 wins the tie break
    # on best rank. Doc 1 has ranks (1, 3), same score as doc 3; best rank
    # ties at 1, so the smaller id wins: order is 1, 3, 2.
    assert fused == [1, 3, 2]
    assert rrf_fuse([[5]], k_const=60) == [5]
