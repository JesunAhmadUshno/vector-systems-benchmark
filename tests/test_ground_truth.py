import numpy as np

from vectorbench.ground_truth import exact_topk


def _normalized(rng, n, d):
    v = rng.standard_normal((n, d)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def test_exact_topk_matches_manual():
    rng = np.random.default_rng(0)
    vectors = _normalized(rng, 50, 16)
    queries = _normalized(rng, 3, 16)
    gt = exact_topk(vectors, queries, 5)
    sims = queries @ vectors.T
    for row in range(3):
        manual = sorted(range(50), key=lambda j: (-float(sims[row, j]), j))[:5]
        assert gt[row] == manual


def test_exact_topk_respects_mask():
    rng = np.random.default_rng(1)
    vectors = _normalized(rng, 40, 8)
    queries = _normalized(rng, 2, 8)
    mask = np.zeros(40, dtype=bool)
    mask[[3, 7, 11, 19, 23, 31]] = True
    gt = exact_topk(vectors, queries, 4, mask=mask)
    for row in gt:
        assert len(row) == 4
        assert all(mask[j] for j in row)


def test_exact_topk_empty_mask():
    rng = np.random.default_rng(2)
    vectors = _normalized(rng, 10, 4)
    queries = _normalized(rng, 2, 4)
    gt = exact_topk(vectors, queries, 3, mask=np.zeros(10, dtype=bool))
    assert gt == [[], []]
