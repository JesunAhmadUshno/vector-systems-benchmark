"""pgvector adapter: PostgreSQL with the pgvector extension.

Setup choices (research pack rows 7, 8, 10, 13):
- HNSW index with m = 32, ef_construction = 200; B-tree indexes on the
  metadata columns.
- Filtering is a SQL WHERE clause. The index is scanned first and the
  filter applied after, which is exactly the overfiltering mechanism the
  study measures.
- Two filter modes are exposed: defaults (iterative scan off,
  hnsw.ef_search = 40, the trap configuration) and iterative (iterative
  scan relaxed_order with a large max_scan_tuples, the documented fix).
- Hybrid is the native product path: tsvector full-text ranking fused
  with vector ranking by RRF inside SQL (pack row 13).
"""

from __future__ import annotations

import numpy as np
import psycopg

from .base import Adapter, FilterSpec


def _vec_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vec) + "]"


class PgvectorAdapter(Adapter):
    name = "pgvector"

    def __init__(self, conninfo: str, dim: int):
        self.conn = psycopg.connect(conninfo, autocommit=True)
        self.dim = dim
        self.ef_search: int | None = 40
        self.iterative = False
        self.max_scan_tuples = 20000
        cur = self.conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("DROP TABLE IF EXISTS chunks")
        cur.execute(
            f"""
            CREATE TABLE chunks (
                id integer PRIMARY KEY,
                embedding vector({dim}),
                tenant text,
                article text,
                paragraph_uid integer,
                content text,
                tsv tsvector
            )
            """
        )

    def create_indexes(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "CREATE INDEX chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 32, ef_construction = 200)"
        )
        cur.execute("CREATE INDEX chunks_tenant ON chunks (tenant)")
        cur.execute("CREATE INDEX chunks_article ON chunks (article)")
        cur.execute("CREATE INDEX chunks_tsv ON chunks USING gin (tsv)")

    def _insert_rows(self, ids, vectors, payloads) -> None:
        rows = [
            (
                int(ext_id),
                _vec_literal(vectors[j]),
                payloads[j]["tenant"],
                payloads[j]["article"],
                int(payloads[j]["paragraph_uid"]),
                payloads[j]["text"],
            )
            for j, ext_id in enumerate(ids)
        ]
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (id, embedding, tenant, article, paragraph_uid, content, tsv) "
                "VALUES (%s, %s::vector, %s, %s, %s, %s, to_tsvector('english', %s)) "
                "ON CONFLICT (id) DO NOTHING",
                [(r[0], r[1], r[2], r[3], r[4], r[5], r[5]) for r in rows],
            )

    def build(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._insert_rows(ids, vectors, payloads)
        self.create_indexes()

    def insert(self, ids: list[int], vectors: np.ndarray, payloads: list[dict]) -> None:
        self._insert_rows(ids, vectors, payloads)

    def delete(self, ids: list[int]) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE id = ANY(%s)", (list(map(int, ids)),))

    def set_breadth(self, value: int) -> None:
        self.ef_search = value

    def set_mode(self, iterative: bool, max_scan_tuples: int = 20000) -> None:
        self.iterative = iterative
        self.max_scan_tuples = max_scan_tuples

    def _apply_settings(self, cur) -> None:
        if self.ef_search is not None:
            cur.execute("SELECT set_config('hnsw.ef_search', %s, false)", (str(self.ef_search),))
        if self.iterative:
            cur.execute("SELECT set_config('hnsw.iterative_scan', 'relaxed_order', false)")
            cur.execute(
                "SELECT set_config('hnsw.max_scan_tuples', %s, false)",
                (str(self.max_scan_tuples),),
            )
        else:
            cur.execute("SELECT set_config('hnsw.iterative_scan', 'off', false)")

    def _where(self, filter_spec: FilterSpec) -> tuple[str, list]:
        if filter_spec is None:
            return "", []
        kind = filter_spec[0]
        if kind == "tenant":
            return "WHERE tenant = %s", [filter_spec[1]]
        if kind == "article_in":
            return "WHERE article = ANY(%s)", [list(filter_spec[1])]
        raise ValueError(f"unsupported filter for pgvector: {kind}")

    def search(self, qvec: np.ndarray, k: int, filter_spec: FilterSpec = None) -> list[int]:
        where, params = self._where(filter_spec)
        with self.conn.cursor() as cur:
            self._apply_settings(cur)
            cur.execute(
                f"SELECT id FROM chunks {where} ORDER BY embedding <=> %s::vector LIMIT %s",
                (*params, _vec_literal(qvec), k),
            )
            return [int(r[0]) for r in cur.fetchall()]

    def hybrid_search(self, qvec: np.ndarray, query_text: str, k: int, depth: int = 100) -> list[int]:
        """Native hybrid: vector ranking and ts_rank ranking fused by RRF in SQL."""
        with self.conn.cursor() as cur:
            self._apply_settings(cur)
            cur.execute(
                """
                WITH dense AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS r
                    FROM chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                ),
                lex AS (
                    SELECT id, ROW_NUMBER() OVER (
                        ORDER BY ts_rank(tsv, plainto_tsquery('english', %s)) DESC
                    ) AS r
                    FROM chunks
                    WHERE tsv @@ plainto_tsquery('english', %s)
                    LIMIT %s
                ),
                fused AS (
                    SELECT id, SUM(1.0 / (60 + r)) AS score
                    FROM (SELECT id, r FROM dense UNION ALL SELECT id, r FROM lex) u
                    GROUP BY id
                )
                SELECT id FROM fused ORDER BY score DESC, id ASC LIMIT %s
                """,
                (
                    _vec_literal(qvec), _vec_literal(qvec), depth,
                    query_text, query_text, depth,
                    k,
                ),
            )
            return [int(r[0]) for r in cur.fetchall()]

    def dense_ranking(self, qvec: np.ndarray, depth: int) -> list[int]:
        return self.search(qvec, depth)

    def close(self) -> None:
        self.conn.close()
