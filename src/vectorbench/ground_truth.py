"""Exact brute-force ground truth.

Ground truth is the contract every recall number is measured against. It is
computed with NumPy over L2-normalized vectors (cosine as inner product)
and knows nothing about any backend.
"""

from __future__ import annotations

import numpy as np


def exact_topk(
    vectors: np.ndarray,
    queries: np.ndarray,
    k: int,
    mask: np.ndarray | None = None,
) -> list[list[int]]:
    """Exact top-k row indices of `vectors` for each query row.

    vectors: (n, d) float32, L2-normalized.
    queries: (m, d) float32, L2-normalized.
    mask: optional boolean (n,) array; only rows with mask True are
    eligible. Filtered ground truth is exact search inside the subset.
    Returns row indices into `vectors`, best first. Ties are broken by the
    smaller row index, deterministically.
    """
    if mask is not None:
        eligible = np.flatnonzero(mask)
    else:
        eligible = np.arange(vectors.shape[0])
    if eligible.size == 0:
        return [[] for _ in range(queries.shape[0])]
    sub = vectors[eligible]
    sims = queries @ sub.T  # (m, e) cosine similarities
    take = min(k, eligible.size)
    # argpartition for speed, then a full sort of the candidates by
    # (-similarity, row index) for a deterministic order.
    part = np.argpartition(-sims, take - 1, axis=1)[:, :take]
    out: list[list[int]] = []
    for row in range(queries.shape[0]):
        cand = part[row]
        cand_rows = eligible[cand]
        cand_sims = sims[row, cand]
        order = sorted(range(take), key=lambda j: (-float(cand_sims[j]), int(cand_rows[j])))
        out.append([int(cand_rows[j]) for j in order])
    return out
