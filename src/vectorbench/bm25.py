"""One shared BM25 implementation.

The same tokenizer, the same idf, and the same term weighting feed every
hybrid arm in the study, so hybrid differences cannot come from the sparse
encoder. The only named exception is the pgvector arm, whose lexical side
is PostgreSQL full-text search by design (the native product path); that
exception is recorded in METHODS.md.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. One tokenizer for the whole study."""
    return _TOKEN_RE.findall(text.lower())


class BM25:
    """Okapi BM25 with the standard +0.5 idf smoothing (Robertson)."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.doc_tf: list[Counter] = []
        self.n_docs: int = 0
        self.postings: dict[str, list[tuple[int, float]]] = {}

    def fit(self, texts: list[str]) -> "BM25":
        self.n_docs = len(texts)
        df: Counter = Counter()
        total_len = 0
        self.doc_tf = []
        self.doc_len = []
        for text in texts:
            tokens = tokenize(text)
            tf = Counter(tokens)
            self.doc_tf.append(tf)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            for term in tf:
                df[term] += 1
        self.avgdl = total_len / self.n_docs if self.n_docs else 0.0
        terms = sorted(df.keys())
        self.vocab = {term: i for i, term in enumerate(terms)}
        n = self.n_docs
        self.idf = {
            term: math.log(1.0 + (n - df[term] + 0.5) / (df[term] + 0.5)) for term in terms
        }
        # Weighted postings: the BM25 weight of a term in a document is
        # fixed at fit time, so precompute it once and let topk accumulate
        # plain floats.
        postings: dict[str, list[tuple[int, float]]] = {}
        for doc_idx, tf in enumerate(self.doc_tf):
            dl = self.doc_len[doc_idx]
            for term, count in tf.items():
                postings.setdefault(term, []).append(
                    (doc_idx, self.term_weight(term, count, dl))
                )
        self.postings = postings
        return self

    def term_weight(self, term: str, tf: int, doc_len: int) -> float:
        """BM25 weight of one term in one document."""
        if term not in self.idf:
            return 0.0
        denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl if self.avgdl else 1.0))
        return self.idf[term] * (tf * (self.k1 + 1.0)) / denom

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        tf = self.doc_tf[doc_idx]
        dl = self.doc_len[doc_idx]
        return sum(self.term_weight(t, tf.get(t, 0), dl) for t in set(query_tokens))

    def topk(self, query_text: str, k: int, allowed: set[int] | None = None) -> list[int]:
        """Top-k document indices for a query, best first.

        Only documents that share at least one query term can score above
        zero, so scoring walks the postings of the query terms instead of
        the whole corpus.
        """
        # Accumulate over the weighted postings of the distinct query
        # terms. This is the same sum score() computes, term by term.
        acc: dict[int, float] = {}
        for term in set(tokenize(query_text)):
            if term not in self.idf:
                continue
            for doc_idx, w in self.postings.get(term, []):
                acc[doc_idx] = acc.get(doc_idx, 0.0) + w
        if allowed is not None:
            acc = {d: s for d, s in acc.items() if d in allowed}
        scored = sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))
        return [d for d, _s in scored[:k]]

    def doc_sparse(self, doc_idx: int) -> tuple[list[int], list[float]]:
        """Sparse vector (vocabulary indices, BM25 weights) for one document."""
        tf = self.doc_tf[doc_idx]
        dl = self.doc_len[doc_idx]
        indices: list[int] = []
        values: list[float] = []
        for term, count in tf.items():
            w = self.term_weight(term, count, dl)
            if w > 0.0:
                indices.append(self.vocab[term])
                values.append(float(w))
        return indices, values

    def query_sparse(self, query_text: str) -> tuple[list[int], list[float]]:
        """Sparse vector for a query: idf weights over its distinct terms."""
        indices: list[int] = []
        values: list[float] = []
        for term in set(tokenize(query_text)):
            if term in self.vocab:
                indices.append(self.vocab[term])
                values.append(float(self.idf[term]))
        return indices, values

    def text_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """Sparse vector for a text that was not part of fit (churn inserts).

        Uses the fitted idf and the text's own length, so weights are on
        the same scale as doc_sparse weights.
        """
        tokens = tokenize(text)
        tf = Counter(tokens)
        indices: list[int] = []
        values: list[float] = []
        for term, count in tf.items():
            w = self.term_weight(term, count, len(tokens))
            if w > 0.0 and term in self.vocab:
                indices.append(self.vocab[term])
                values.append(float(w))
        return indices, values
