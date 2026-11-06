"""Qdrant adapter: qdrant-client in embedded local mode (in memory).

Setup choices (research pack rows 14, 17, 18):
- Payload indexes on `tenant` and `article` are created before ingestion,
  so filter-aware graph edges can be built during indexing. The client
  itself warns that payload indexes have no effect in local mode; the
  call is kept so the harness mirrors the server setup, and the warning
  is recorded in AUDIT.md.
- Points carry a dense vector and a sparse vector built from the shared
  BM25 encoder. The hybrid arm uses the Query API with RRF fusion.
- Deletes are tombstones in the real engine; local mode applies the same
  visible semantics: a deleted point never returns in search.

Local mode is an embedded implementation, not the network server. Its
latency excludes network cost and its internals differ from the server
build. SPEC.md names this as a limitation wherever latency is quoted.
The in-memory variant is used because the on-disk variant's SQLite
write path ingested about 1,000 points per minute on this VM (measured:
26,622 of 58,999 points in about 27 minutes), which made the full study
impractical; the local engine and its semantics are the same in both
variants. See DECISIONS.md, D8.
"""

from __future__ import annotations

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client import models as qm

from .base import Adapter, FilterSpec

COLLECTION = "chunks"


class QdrantAdapter(Adapter):
    name = "qdrant"

    def __init__(self, path: str | None, dim: int, bm25=None, m: int = 32, ef_construct: int = 200):
        self.client = QdrantClient(location=":memory:") if path is None else QdrantClient(path=path)
        self.dim = dim
        self.bm25 = bm25
        self.hnsw_ef: int | None = None
        self.native_hybrid_ok: bool | None = None
        if self.client.collection_exists(COLLECTION):
            self.client.delete_collection(COLLECTION)
        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": qm.VectorParams(
                    size=dim,
                    distance=qm.Distance.COSINE,
                    hnsw_config=qm.HnswConfigDiff(m=m, ef_construct=ef_construct),
                )
            },
            sparse_vectors_config={"sparse": qm.SparseVectorParams()},
        )
        # Payload indexes before ingestion (pack row 14).
        self.client.create_payload_index(COLLECTION, "tenant", qm.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(COLLECTION, "article", qm.PayloadSchemaType.KEYWORD)

    def _points(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]):
        points = []
        for j, ext_id in enumerate(ids):
            vector: dict = {"dense": vectors[j].astype(float).tolist()}
            if self.bm25 is not None:
                if "_corpus_row" in payloads[j]:
                    s_idx, s_val = self.bm25.doc_sparse(payloads[j]["_corpus_row"])
                else:
                    s_idx, s_val = self.bm25.text_sparse(payloads[j]["text"])
                if s_idx:
                    vector["sparse"] = qm.SparseVector(indices=s_idx, values=s_val)
            points.append(
                qm.PointStruct(
                    id=int(ext_id),
                    vector=vector,
                    payload={"tenant": payloads[j]["tenant"], "article": payloads[j]["article"]},
                )
            )
        return points

    def _upsert(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        # Large batches: local mode stores points in SQLite, and small
        # transactions carry heavy journal and page-rewrite costs on this
        # filesystem. 4096 points per call measured far faster per point.
        batch = 4096
        for start in range(0, len(ids), batch):
            pts = self._points(ids[start:start + batch], vectors[start:start + batch], payloads[start:start + batch])
            self.client.upsert(collection_name=COLLECTION, points=pts, wait=True)

    def build(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._upsert(ids, vectors, payloads)

    def insert(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._upsert(ids, vectors, payloads)

    def delete(self, ids: list[int]) -> None:
        self.client.delete(
            collection_name=COLLECTION,
            points_selector=qm.PointIdsList(points=[int(i) for i in ids]),
            wait=True,
        )

    def set_breadth(self, value: int) -> None:
        self.hnsw_ef = value

    def _filter(self, filter_spec: FilterSpec) -> qm.Filter | None:
        if filter_spec is None:
            return None
        kind = filter_spec[0]
        if kind == "tenant":
            return qm.Filter(must=[qm.FieldCondition(key="tenant", match=qm.MatchValue(value=filter_spec[1]))])
        if kind == "article_in":
            return qm.Filter(must=[qm.FieldCondition(key="article", match=qm.MatchAny(any=list(filter_spec[1])))])
        raise ValueError(f"unsupported filter for qdrant: {kind}")

    def _params(self) -> qm.SearchParams | None:
        if self.hnsw_ef is None:
            return None
        return qm.SearchParams(hnsw_ef=self.hnsw_ef)

    def search(self, qvec: np.ndarray, k: int, filter_spec: FilterSpec = None) -> list[int]:
        res = self.client.query_points(
            collection_name=COLLECTION,
            query=qvec.astype(float).tolist(),
            using="dense",
            query_filter=self._filter(filter_spec),
            search_params=self._params(),
            limit=k,
        )
        return [int(p.id) for p in res.points]

    def search_sparse(self, sparse: tuple[list[int], list[float]], k: int) -> list[int]:
        indices, values = sparse
        if not indices:
            return []
        res = self.client.query_points(
            collection_name=COLLECTION,
            query=qm.SparseVector(indices=indices, values=values),
            using="sparse",
            limit=k,
        )
        return [int(p.id) for p in res.points]

    def hybrid_search(self, qvec: np.ndarray, sparse: tuple[list[int], list[float]], k: int) -> list[int]:
        """Native Query API fusion (RRF). Raises if local mode rejects it."""
        s_idx, s_val = sparse
        res = self.client.query_points(
            collection_name=COLLECTION,
            prefetch=[
                qm.Prefetch(query=qvec.astype(float).tolist(), using="dense", limit=100),
                qm.Prefetch(query=qm.SparseVector(indices=s_idx, values=s_val), using="sparse", limit=100),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=k,
        )
        return [int(p.id) for p in res.points]

    def close(self) -> None:
        self.client.close()
