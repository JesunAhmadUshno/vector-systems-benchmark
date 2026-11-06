"""The shared adapter interface.

A filter spec is one of:
- None: no filter.
- ("tenant", value): the tenant field equals value.
- ("article_in", [name, ...]): the article field is one of the names.
- ("exclude", {id, ...}): every id except these (FAISS churn bookkeeping).

Every adapter translates the same spec, so a cell means the same thing on
every backend.
"""

from __future__ import annotations

import numpy as np

FilterSpec = tuple | None


class Adapter:
    name = "base"

    def build(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        raise NotImplementedError

    def search(self, qvec: np.ndarray, k: int, filter_spec: FilterSpec = None) -> list[int]:
        raise NotImplementedError

    def delete(self, ids: list[int]) -> None:
        raise NotImplementedError

    def insert(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        raise NotImplementedError

    def set_breadth(self, value: int) -> None:
        """Set the search breadth knob (efSearch, hnsw_ef, hnsw.ef_search)."""
        raise NotImplementedError

    def close(self) -> None:
        pass
