"""FAISS adapter: IndexHNSWFlat in process.

Facts that shape this adapter (research pack rows 2 and 6):
- The HNSW graph cannot remove points. Deletes are recorded, and search
  either ignores the record (the raw arm, where deleted ids can return)
  or excludes the deleted positions with an IDSelector (the bookkeeping
  arm). Both arms are measured.
- Filtering is an IDSelectorBatch over the allowed positions, passed at
  search time.
"""

from __future__ import annotations

import faiss
import numpy as np

from .base import Adapter, FilterSpec


class FaissAdapter(Adapter):
    name = "faiss"

    def __init__(self, dim: int, m: int = 32, ef_construction: int = 200):
        self.dim = dim
        self.index = faiss.IndexHNSWFlat(dim, m)
        self.index.hnsw.efConstruction = ef_construction
        self.ef_search = 40
        self.ids: list[int] = []              # position -> external id
        self.pos_of: dict[int, int] = {}      # external id -> position
        self.tenants: list[str] = []          # position -> tenant
        self.articles: list[str] = []         # position -> article
        self.deleted: set[int] = set()        # external ids marked deleted
        self.bookkeeping = False              # exclusion arm on or off

    def _add(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        base = len(self.ids)
        self.index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        for j, ext_id in enumerate(ids):
            self.pos_of[ext_id] = base + j
            self.ids.append(ext_id)
            self.tenants.append(payloads[j]["tenant"])
            self.articles.append(payloads[j]["article"])

    def build(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._add(ids, vectors, payloads)

    def insert(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._add(ids, vectors, payloads)

    def delete(self, ids: list[int]) -> None:
        # HNSW cannot remove points. The ids are only recorded; whether a
        # search honours the record is the bookkeeping flag.
        self.deleted.update(ids)

    def set_breadth(self, value: int) -> None:
        self.ef_search = value

    def _selector(self, filter_spec: FilterSpec):
        allowed_positions: list[int] | None = None
        if filter_spec is not None:
            kind = filter_spec[0]
            if kind == "tenant":
                allowed_positions = [p for p, t in enumerate(self.tenants) if t == filter_spec[1]]
            elif kind == "article_in":
                wanted = set(filter_spec[1])
                allowed_positions = [p for p, a in enumerate(self.articles) if a in wanted]
            elif kind == "exclude":
                excluded = set(filter_spec[1])
                allowed_positions = [
                    p for p, ext in enumerate(self.ids) if ext not in excluded
                ]
        if self.bookkeeping and self.deleted:
            deleted_pos = {self.pos_of[d] for d in self.deleted if d in self.pos_of}
            if allowed_positions is None:
                allowed_positions = [p for p in range(len(self.ids)) if p not in deleted_pos]
            else:
                allowed_positions = [p for p in allowed_positions if p not in deleted_pos]
        if allowed_positions is None:
            return None
        arr = np.array(sorted(allowed_positions), dtype=np.int64)
        return faiss.IDSelectorBatch(arr)

    def search(self, qvec: np.ndarray, k: int, filter_spec: FilterSpec = None) -> list[int]:
        selector = self._selector(filter_spec)
        params = faiss.SearchParametersHNSW()
        params.efSearch = self.ef_search
        if selector is not None:
            params.sel = selector
        q = np.ascontiguousarray(qvec.reshape(1, -1), dtype=np.float32)
        _dists, idx = self.index.search(q, k, params=params)
        return [self.ids[int(p)] for p in idx[0] if p >= 0]
