"""Amendment D11: paired per-question bootstrap for the hybrid gains.

Registered in DECISIONS.md (D11) on 2026-11-16 BEFORE this code ran.
Replicates the registered hybrid cell (same corpus, embeddings,
question sample with QUERY_SEED, relevance rule, RRF k = 60) while
recording per-question nDCG@10 for the dense, shared-BM25, and
hybrid arms, then bootstraps the hybrid-minus-dense gain per
backend: 2,000 resamples over the scored questions, seed 20261116,
percentile 95 percent interval.

Validation rule from the registration: each arm's aggregate
nDCG@10 must reproduce the committed results/cells.json value
within 0.001, or the interval for that backend is not reported.

Scope: FAISS and Qdrant arms. The pgvector hybrid arm runs inside
PostgreSQL, unavailable in the reproduction environment, so its
per-question scores cannot be regenerated; its gain keeps its
aggregate-only status.

Output: results/amendment_d11.json (path set by --out).
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np

from .run_benchmark import (
    Study, prepare, payloads_for, QUERY_SEED,
)
from .metrics import ndcg_at_k, rrf_fuse

BOOT_SEED = 20261116
BOOT_N = 2000


def hybrid_per_question(bundle, study, dense_fn, hybrid_fn=None):
    """hybrid_generic's loop, verbatim scoring, per-question capture."""
    meta = bundle["meta"]
    bm25 = bundle["bm25"]
    rng = random.Random(QUERY_SEED)
    questions = meta["questions"]
    sample_idx = rng.sample(range(len(questions)), min(250, len(questions)))
    by_para: dict[int, list[int]] = {}
    for c in study.chunks:
        by_para.setdefault(c["paragraph_uid"], []).append(c["id"])
    qvecs = bundle["question_vecs"]
    dense_ndcg, hyb_ndcg, bm_ndcg = [], [], []
    for qi in sample_idx:
        q = questions[qi]
        relevant = set(by_para.get(q["paragraph_uid"], []))
        if not relevant:
            continue
        qvec = qvecs[qi]
        dense = dense_fn(qvec, 100)
        bm_rows = bm25.topk(q["question"], 100)
        bm_ids = [study.chunks[r]["id"] for r in bm_rows]
        if hybrid_fn is not None:
            hyb = hybrid_fn(qvec, q["question"], 100)
        else:
            hyb = rrf_fuse([dense, bm_ids], k_const=60)[:100]
        dense_ndcg.append(ndcg_at_k(dense, relevant, 10))
        bm_ndcg.append(ndcg_at_k(bm_ids, relevant, 10))
        hyb_ndcg.append(ndcg_at_k(hyb, relevant, 10))
    return (np.array(dense_ndcg), np.array(bm_ndcg), np.array(hyb_ndcg))


def bootstrap_gain(dense, hyb):
    gain = hyb - dense
    rng = np.random.default_rng(BOOT_SEED)
    n = len(gain)
    means = np.empty(BOOT_N)
    for i in range(BOOT_N):
        idx = rng.integers(0, n, n)
        means[i] = gain[idx].mean()
    return {
        "n_questions": int(n),
        "point_gain": round(float(gain.mean()), 6),
        "bootstrap_mean_gain": round(float(means.mean()), 6),
        "ci95_percentile": [round(float(np.percentile(means, 2.5)), 6),
                            round(float(np.percentile(means, 97.5)), 6)],
        "aggregate_ndcg10": {
            "dense": round(float(dense.mean()), 6),
            "hybrid": round(float(hyb.mean()), 6),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--committed", default="results/cells.json")
    ap.add_argument("--out", default="results/amendment_d11.json")
    ap.add_argument("--backends", default="faiss,qdrant")
    args = ap.parse_args()

    committed = json.loads(Path(args.committed).read_text())
    bundle = prepare(Path(args.data_dir))
    out = {"registered_in": "DECISIONS.md D11 (2026-11-16, before this run)",
           "status": "exploratory post-hoc amendment; H6 verdict unchanged",
           "backends": {}}

    for backend in [b.strip() for b in args.backends.split(",") if b.strip()]:
        study = Study(bundle, n_queries=300, reps=3)
        if backend == "faiss":
            from .adapters.faiss_adapter import FaissAdapter
            ad = FaissAdapter(dim=study.dim)
            ids = [c["id"] for c in study.chunks]
            ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
            dense, bm, hyb = hybrid_per_question(
                bundle, study,
                dense_fn=lambda qvec, depth: ad.search(qvec, depth))
            ad.close()
        elif backend == "qdrant":
            from .adapters.qdrant_adapter import QdrantAdapter
            ad = QdrantAdapter(path=None, dim=study.dim, bm25=bundle["bm25"])
            ids = [c["id"] for c in study.chunks]
            ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
            bm25 = bundle["bm25"]

            def native_hybrid(qvec, qtext, depth):
                s_idx, s_val = bm25.query_sparse(qtext)
                return ad.hybrid_search(qvec, (s_idx, s_val), depth)

            dense, bm, hyb = hybrid_per_question(
                bundle, study,
                dense_fn=lambda qvec, depth: ad.search(qvec, depth),
                hybrid_fn=native_hybrid)
            ad.close()
        else:
            raise ValueError(backend)

        res = bootstrap_gain(dense, hyb)
        ref = committed["hybrid"][backend]["arms"]
        res["validation_vs_committed"] = {
            "dense_committed": ref["dense"]["ndcg10"],
            "hybrid_committed": ref["hybrid"]["ndcg10"],
            "dense_reproduced_within_0.001":
                abs(res["aggregate_ndcg10"]["dense"] - ref["dense"]["ndcg10"]) <= 0.001,
            "hybrid_reproduced_within_0.001":
                abs(res["aggregate_ndcg10"]["hybrid"] - ref["hybrid"]["ndcg10"]) <= 0.001,
        }
        out["backends"][backend] = res
        print(backend, json.dumps(res), flush=True)

    out["pgvector"] = {
        "status": "not covered: the pgvector hybrid arm runs inside "
                  "PostgreSQL, unavailable in this environment; its "
                  "gain (plus 0.017, aggregate) keeps its "
                  "aggregate-only status."}
    Path(args.out).write_text(json.dumps(out, indent=1))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
