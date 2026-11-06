"""Benchmark runner.

Pipeline: prepare corpus and embeddings (cached), then per backend:
build, tune breadth on the unfiltered cell, run the regime cells, run the
hybrid cell, run backend-specific cells (the pgvector trap), apply churn,
run the post-churn cells. Every number lands in results/*.json. RESULTS.md
is built from those files by generate_results.py, never by hand.

Usage:
    python -m vectorbench.run_benchmark --backends faiss,qdrant,pgvector
    python -m vectorbench.run_benchmark --prepare-only
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from .bm25 import BM25
from .corpus import (
    CHURN_SEED,
    QUERY_SEED,
    SQUAD_LICENCE,
    TENANT_NAMES,
    TENANT_PROBS,
    Chunk,
    build_corpus,
    download_squad,
    pick_article_group,
)
from .embed import MODEL_LICENCE, MODEL_NAME, embed_texts
from .ground_truth import exact_topk
from .metrics import (
    mean_returned,
    ndcg_at_k,
    percentiles_ms,
    recall_at_depth,
    recall_at_k,
    rrf_fuse,
    shortfall_rate,
    stale_rate,
)

K = 10
BREADTH_LADDER = [40, 80, 120, 200, 320]
MAIN_CELLS = ["none", "tenant_t0", "tenant_t2", "tenant_t5", "article_group"]
DEFAULT_PG_CONNINFO = "dbname=vsbench host=/var/run/postgresql user=postgres"


# --------------------------------------------------------------------------
# Preparation
# --------------------------------------------------------------------------

def prepare(data_dir: Path) -> dict:
    """Build or load the corpus, embeddings and BM25. Returns a bundle."""
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_path = data_dir / "corpus_meta.json"
    emb_path = data_dir / "embeddings.npz"
    if meta_path.exists() and emb_path.exists():
        meta = json.loads(meta_path.read_text())
        z = np.load(emb_path)
        bundle = {
            "meta": meta,
            "corpus_vecs": z["corpus"],
            "heldout_vecs": z["heldout"],
            "question_vecs": z["questions"],
        }
    else:
        squad = download_squad(data_dir / "squad_train_v1.1.json")
        corpus = build_corpus(squad, window=30)
        corpus_vecs = embed_texts([c.text for c in corpus.chunks])
        heldout_vecs = embed_texts([c.text for c in corpus.heldout_chunks])
        question_vecs = embed_texts([q["question"] for q in corpus.questions])
        meta = {
            "window_words": corpus.window_words,
            "n_paragraphs": corpus.n_paragraphs,
            "n_heldout_paragraphs": corpus.n_heldout_paragraphs,
            "chunks": [
                {"id": c.id, "text": c.text, "article": c.article,
                 "paragraph_uid": c.paragraph_uid, "tenant": c.tenant}
                for c in corpus.chunks
            ],
            "heldout": [
                {"id": c.id, "text": c.text, "article": c.article,
                 "paragraph_uid": c.paragraph_uid}
                for c in corpus.heldout_chunks
            ],
            "questions": corpus.questions,
            "dim": int(corpus_vecs.shape[1]),
        }
        meta_path.write_text(json.dumps(meta))
        np.savez_compressed(
            emb_path, corpus=corpus_vecs, heldout=heldout_vecs, questions=question_vecs
        )
        bundle = {
            "meta": meta,
            "corpus_vecs": corpus_vecs,
            "heldout_vecs": heldout_vecs,
            "question_vecs": question_vecs,
        }
    bundle["bm25"] = BM25().fit([c["text"] for c in bundle["meta"]["chunks"]])
    return bundle


def payloads_for(meta_chunks: list[dict], with_row: bool = True) -> list[dict]:
    out = []
    for row, c in enumerate(meta_chunks):
        p = {
            "tenant": c["tenant"],
            "article": c["article"],
            "paragraph_uid": c["paragraph_uid"],
            "text": c["text"],
        }
        if with_row:
            p["_corpus_row"] = row
        out.append(p)
    return out


def insert_payloads(inserts: list[dict]) -> list[dict]:
    return [
        {"tenant": i["tenant"], "article": i["article"],
         "paragraph_uid": i["paragraph_uid"], "text": i["text"]}
        for i in inserts
    ]


# --------------------------------------------------------------------------
# Study state: vectors by id, live set, filters, ground truth
# --------------------------------------------------------------------------

class Study:
    def __init__(self, bundle: dict, n_queries: int, reps: int):
        meta = bundle["meta"]
        self.meta = meta
        self.chunks = meta["chunks"]
        self.heldout = meta["heldout"]
        self.n = len(self.chunks)
        self.dim = meta["dim"]
        # Row index equals external id for every chunk (ids are sequential).
        total = self.n + len(self.heldout)
        self.vec_by_id = np.zeros((total, self.dim), dtype=np.float32)
        self.vec_by_id[: self.n] = bundle["corpus_vecs"]
        self.vec_by_id[self.n:] = bundle["heldout_vecs"]
        self.live = np.zeros(total, dtype=bool)
        self.live[: self.n] = True
        self.article_of = {c["id"]: c["article"] for c in self.chunks}
        self.tenant_of = {c["id"]: c["tenant"] for c in self.chunks}
        self.query_ids = [h["id"] for h in self.heldout[:n_queries]]
        self.queries = self.vec_by_id[self.query_ids]
        self.reps = reps

        def share(pred) -> float:
            return float(np.mean([pred(c) for c in self.chunks]))

        group = pick_article_group(
            [Chunk(id=c["id"], text="", article=c["article"],
                   paragraph_uid=c["paragraph_uid"], tenant=c["tenant"])
             for c in self.chunks],
            0.01,
        )
        self.article_group = group
        self.filters = {
            "none": (None, 1.0),
            "tenant_t0": (("tenant", "t0"), share(lambda c: c["tenant"] == "t0")),
            "tenant_t2": (("tenant", "t2"), share(lambda c: c["tenant"] == "t2")),
            "tenant_t5": (("tenant", "t5"), share(lambda c: c["tenant"] == "t5")),
            "article_group": (
                ("article_in", group),
                share(lambda c: c["article"] in set(group)),
            ),
        }

    def mask_for(self, filter_spec) -> np.ndarray:
        mask = self.live.copy()
        if filter_spec is None:
            return mask
        kind = filter_spec[0]
        ids = np.arange(len(mask))
        if kind == "tenant":
            keep = np.array([self.tenant_of.get(int(i)) == filter_spec[1] for i in ids])
        elif kind == "article_in":
            wanted = set(filter_spec[1])
            keep = np.array([self.article_of.get(int(i)) in wanted for i in ids])
        else:
            raise ValueError(f"unknown filter kind {kind}")
        return mask & keep

    def ground_truth(self, filter_spec, k: int = K) -> list[list[int]]:
        return exact_topk(self.vec_by_id, self.queries, k, mask=self.mask_for(filter_spec))


# --------------------------------------------------------------------------
# Cell machinery
# --------------------------------------------------------------------------

def run_cell(adapter, study: Study, label: str, filter_spec, selectivity) -> dict:
    gt = study.ground_truth(filter_spec)
    recall_runs: list[float] = []
    lat_runs: list[list[float]] = []
    first_returned = None
    for _rep in range(study.reps):
        returned = []
        lat = []
        for q in study.queries:
            t0 = time.perf_counter()
            out = adapter.search(q, K, filter_spec)
            lat.append((time.perf_counter() - t0) * 1000.0)
            returned.append(out)
        recall_runs.append(recall_at_k(returned, gt, K))
        lat_runs.append(lat)
        if first_returned is None:
            first_returned = returned
    median_rep = int(np.argsort([sum(l) for l in lat_runs])[len(lat_runs) // 2])
    pct = percentiles_ms(lat_runs[median_rep])
    return {
        "cell": label,
        "filter": repr(filter_spec),
        "selectivity": selectivity,
        "n_queries": len(study.query_ids),
        "recall10": recall_runs[0],
        "recall_runs": recall_runs,
        "shortfall_rate": shortfall_rate(first_returned, K),
        "mean_returned": mean_returned(first_returned),
        "p50_ms": pct["p50"],
        "p95_ms": pct["p95"],
        "reps": study.reps,
        "_returned": first_returned,
    }


def public_cell(cell: dict) -> dict:
    return {k: v for k, v in cell.items() if not k.startswith("_")}


def tune_breadth(adapter, study: Study) -> dict:
    gt = study.ground_truth(None)
    ladder = []
    chosen = BREADTH_LADDER[-1]
    for ef in BREADTH_LADDER:
        adapter.set_breadth(ef)
        returned = [adapter.search(q, K) for q in study.queries]
        r = recall_at_k(returned, gt, K)
        ladder.append({"breadth": ef, "recall10": r})
        if r >= 0.95:
            chosen = ef
            break
    adapter.set_breadth(chosen)
    return {"ladder": ladder, "chosen": chosen}


def run_main_cells(adapter, study: Study, results: dict, backend: str, arm: str) -> None:
    for cell_name in MAIN_CELLS:
        spec, sel = study.filters[cell_name]
        cell = run_cell(adapter, study, cell_name, spec, sel)
        cell["backend"] = backend
        cell["arm"] = arm
        results["cells"].append(public_cell(cell))


# --------------------------------------------------------------------------
# Hybrid cell
# --------------------------------------------------------------------------

def hybrid_generic(bundle, study: Study, dense_fn, hybrid_fn=None, sparse_fn=None) -> dict:
    meta = bundle["meta"]
    bm25: BM25 = bundle["bm25"]
    rng = random.Random(QUERY_SEED)
    questions = meta["questions"]
    sample_idx = rng.sample(range(len(questions)), min(250, len(questions)))
    by_para: dict[int, list[int]] = {}
    for c in study.chunks:
        by_para.setdefault(c["paragraph_uid"], []).append(c["id"])
    qvecs = bundle["question_vecs"]
    dense_ndcg, dense_rec = [], []
    bm_ndcg, bm_rec = [], []
    hyb_ndcg, hyb_rec = [], []
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
        elif sparse_fn is not None:
            sparse = sparse_fn(qvec, q["question"], 100)
            hyb = rrf_fuse([dense, sparse], k_const=60)[:100]
        else:
            hyb = rrf_fuse([dense, bm_ids], k_const=60)[:100]
        dense_ndcg.append(ndcg_at_k(dense, relevant, 10))
        dense_rec.append(recall_at_depth(dense, relevant, 100))
        bm_ndcg.append(ndcg_at_k(bm_ids, relevant, 10))
        bm_rec.append(recall_at_depth(bm_ids, relevant, 100))
        hyb_ndcg.append(ndcg_at_k(hyb, relevant, 10))
        hyb_rec.append(recall_at_depth(hyb, relevant, 100))
    return {
        "n_questions_sampled": len(sample_idx),
        "n_questions_scored": len(dense_ndcg),
        "arms": {
            "dense": {"ndcg10": float(np.mean(dense_ndcg)), "recall100": float(np.mean(dense_rec))},
            "bm25_shared": {"ndcg10": float(np.mean(bm_ndcg)), "recall100": float(np.mean(bm_rec))},
            "hybrid": {"ndcg10": float(np.mean(hyb_ndcg)), "recall100": float(np.mean(hyb_rec))},
        },
    }


# --------------------------------------------------------------------------
# Churn
# --------------------------------------------------------------------------

def churn_setup(study: Study) -> tuple[list[int], list[dict], np.ndarray]:
    rng = random.Random(CHURN_SEED)
    n_del = study.n // 10
    delete_ids = sorted(rng.sample([c["id"] for c in study.chunks], n_del))
    pool = study.heldout[300:300 + n_del]
    tenant_rng = random.Random(CHURN_SEED + 1)
    inserts = []
    for h in pool:
        tenant = tenant_rng.choices(TENANT_NAMES, weights=TENANT_PROBS, k=1)[0]
        inserts.append({
            "id": h["id"], "text": h["text"], "article": h["article"],
            "paragraph_uid": h["paragraph_uid"], "tenant": tenant,
        })
    return delete_ids, inserts, np.array([h["id"] for h in pool], dtype=int)


def apply_churn_to_study(study: Study, delete_ids, inserts) -> None:
    for d in delete_ids:
        study.live[d] = False
    for ins in inserts:
        study.live[ins["id"]] = True
        study.article_of[ins["id"]] = ins["article"]
        study.tenant_of[ins["id"]] = ins["tenant"]


# --------------------------------------------------------------------------
# Per-backend runs
# --------------------------------------------------------------------------

def run_faiss(bundle, study: Study, results: dict) -> None:
    from .adapters.faiss_adapter import FaissAdapter

    ad = FaissAdapter(dim=study.dim)
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
    results["tuning"]["faiss"] = tune_breadth(ad, study)
    run_main_cells(ad, study, results, "faiss", "main")
    h = hybrid_generic(bundle, study, dense_fn=lambda qvec, depth: ad.search(qvec, depth))
    h["fusion"] = "application-level RRF over FAISS dense ranking and shared BM25 ranking"
    results["hybrid"]["faiss"] = h
    # Churn: deletes are marks on the graph; inserts are real adds.
    pre = {c["cell"]: c for c in results["cells"] if c["backend"] == "faiss"}
    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts], study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    for arm, bookkeeping in [("raw", False), ("bookkeeping", True)]:
        ad.bookkeeping = bookkeeping
        for cell_name in ["none", "tenant_t5"]:
            spec, sel = study.filters[cell_name]
            cell = run_cell(ad, study, f"post_churn_{cell_name}", spec, sel)
            cell["backend"] = "faiss"
            cell["arm"] = arm
            cell["stale_rate"] = stale_rate(cell["_returned"], delete_ids)
            cell["pre_churn_recall10"] = pre[cell_name]["recall10"]
            results["churn"].append(public_cell(cell))
    ad.close()


def run_qdrant(bundle, study: Study, results: dict, qdrant_dir: Path) -> None:
    from .adapters.qdrant_adapter import QdrantAdapter

    ad = QdrantAdapter(path=str(qdrant_dir), dim=study.dim, bm25=bundle["bm25"])
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
    results["tuning"]["qdrant"] = tune_breadth(ad, study)
    run_main_cells(ad, study, results, "qdrant", "main")
    bm25: BM25 = bundle["bm25"]

    def native_hybrid(qvec, qtext, depth):
        s_idx, s_val = bm25.query_sparse(qtext)
        return ad.hybrid_search(qvec, (s_idx, s_val), depth)

    try:
        h = hybrid_generic(
            bundle, study,
            dense_fn=lambda qvec, depth: ad.search(qvec, depth),
            hybrid_fn=native_hybrid,
        )
        h["fusion"] = "native Query API RRF"
        h["native_hybrid_ok"] = True
    except Exception as exc:
        h = hybrid_generic(
            bundle, study,
            dense_fn=lambda qvec, depth: ad.search(qvec, depth),
            sparse_fn=lambda qvec, qtext, depth: ad.search_sparse(bm25.query_sparse(qtext), depth),
        )
        h["fusion"] = f"client-side RRF (native fusion failed: {type(exc).__name__}: {exc})"
        h["native_hybrid_ok"] = False
    results["hybrid"]["qdrant"] = h
    pre = {c["cell"]: c for c in results["cells"] if c["backend"] == "qdrant"}
    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts], study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    for cell_name in ["none", "tenant_t5"]:
        spec, sel = study.filters[cell_name]
        cell = run_cell(ad, study, f"post_churn_{cell_name}", spec, sel)
        cell["backend"] = "qdrant"
        cell["arm"] = "native"
        cell["stale_rate"] = stale_rate(cell["_returned"], delete_ids)
        cell["pre_churn_recall10"] = pre[cell_name]["recall10"]
        results["churn"].append(public_cell(cell))
    ad.close()


def run_pgvector(bundle, study: Study, results: dict, conninfo: str) -> None:
    from .adapters.pgvector_adapter import PgvectorAdapter

    ad = PgvectorAdapter(conninfo=conninfo, dim=study.dim)
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks, with_row=False))
    # Main cells run the documented fix: iterative scan on.
    ad.set_mode(iterative=True)
    results["tuning"]["pgvector"] = tune_breadth(ad, study)
    run_main_cells(ad, study, results, "pgvector", "iterative")
    h = hybrid_generic(
        bundle, study,
        dense_fn=lambda qvec, depth: ad.search(qvec, depth),
        hybrid_fn=lambda qvec, qtext, depth: ad.hybrid_search(qvec, qtext, depth),
    )
    h["fusion"] = "SQL RRF over vector ranking and ts_rank ranking"
    results["hybrid"]["pgvector"] = h
    # Trap cells: the defaults an untuned deployment runs.
    ad.set_mode(iterative=False)
    ad.set_breadth(40)
    for cell_name in ["tenant_t2", "tenant_t5"]:
        spec, sel = study.filters[cell_name]
        cell = run_cell(ad, study, f"trap_{cell_name}", spec, sel)
        cell["backend"] = "pgvector"
        cell["arm"] = "trap_defaults"
        results["trap"].append(public_cell(cell))
    ad.set_mode(iterative=True)
    ad.set_breadth(results["tuning"]["pgvector"]["chosen"])
    pre = {c["cell"]: c for c in results["cells"] if c["backend"] == "pgvector"}
    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts], study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    for cell_name in ["none", "tenant_t5"]:
        spec, sel = study.filters[cell_name]
        cell = run_cell(ad, study, f"post_churn_{cell_name}", spec, sel)
        cell["backend"] = "pgvector"
        cell["arm"] = "iterative"
        cell["stale_rate"] = stale_rate(cell["_returned"], delete_ids)
        cell["pre_churn_recall10"] = pre[cell_name]["recall10"]
        results["churn"].append(public_cell(cell))
    ad.close()


# --------------------------------------------------------------------------
# Environment record
# --------------------------------------------------------------------------

def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def env_record(bundle: dict, study: Study) -> dict:
    import faiss
    import qdrant_client

    env = {
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": cpu_model(),
        "numpy": np.__version__,
        "faiss": getattr(faiss, "__version__", "unknown"),
        "qdrant_client": getattr(qdrant_client, "__version__", "unknown"),
        "embedding_model": MODEL_NAME,
        "embedding_model_licence": MODEL_LICENCE,
        "corpus": "SQuAD v1.1 train paragraphs, chunked",
        "corpus_licence": SQUAD_LICENCE,
        "n_chunks": study.n,
        "n_heldout_chunks": len(study.heldout),
        "n_paragraphs": study.meta["n_paragraphs"],
        "n_heldout_paragraphs": study.meta["n_heldout_paragraphs"],
        "window_words": study.meta["window_words"],
        "dim": study.dim,
        "n_queries": len(study.query_ids),
        "reps": study.reps,
        "k": K,
        "tenant_shares_measured": {
            name: float(np.mean([c["tenant"] == name for c in study.chunks]))
            for name in TENANT_NAMES
        },
        "filter_selectivity_measured": {
            name: sel for name, (_spec, sel) in study.filters.items()
        },
        "article_group_for_correlated_cell": study.article_group,
        "breadth_ladder": BREADTH_LADDER,
        "seeds": {"split": 13, "tenant": 42, "churn": CHURN_SEED, "query_sample": QUERY_SEED},
    }
    try:
        import model2vec

        env["model2vec"] = getattr(model2vec, "__version__", "unknown")
    except Exception:
        env["model2vec"] = "unknown"
    return env


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--work-dir", default="work")
    ap.add_argument("--backends", default="faiss,qdrant,pgvector")
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--pg-conninfo", default=DEFAULT_PG_CONNINFO)
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    results_dir = Path(args.results_dir)
    work_dir = Path(args.work_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    bundle = prepare(data_dir)
    study0 = Study(bundle, n_queries=args.queries, reps=args.reps)
    print(f"corpus chunks: {study0.n}, heldout: {len(study0.heldout)}, dim: {study0.dim}")
    print("selectivities:", {k: round(v[1], 4) for k, v in study0.filters.items()})
    if args.prepare_only:
        return 0

    results = {"cells": [], "churn": [], "trap": [], "hybrid": {}, "tuning": {}, "blocked": []}
    env = env_record(bundle, study0)
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]

    def dispatch(name: str, study: Study) -> None:
        if name == "faiss":
            run_faiss(bundle, study, results)
        elif name == "qdrant":
            run_qdrant(bundle, study, results, work_dir / "qdrant")
        elif name == "pgvector":
            run_pgvector(bundle, study, results, args.pg_conninfo)
        else:
            raise ValueError(f"unknown backend {name}")

    for name in backends:
        # Churn mutates the study, so every backend gets a fresh one.
        study = Study(bundle, n_queries=args.queries, reps=args.reps)
        try:
            dispatch(name, study)
            print(f"backend done: {name}", flush=True)
        except Exception as exc:
            traceback.print_exc()
            results["blocked"].append(
                {"backend": name, "error": f"{type(exc).__name__}: {exc}"}
            )
            print(f"backend BLOCKED: {name}: {exc}", flush=True)
        (results_dir / "cells.json").write_text(json.dumps(results, indent=1))

    try:
        import psycopg

        with psycopg.connect(args.pg_conninfo) as conn:
            row = conn.execute("SELECT version()").fetchone()
            env["postgres"] = row[0] if row else "unknown"
            row = conn.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            env["pgvector"] = row[0] if row else "not installed"
    except Exception as exc:
        env["postgres"] = f"unreachable ({type(exc).__name__})"
        env["pgvector"] = "unreachable"
    env["backends_requested"] = backends
    (results_dir / "env.json").write_text(json.dumps(env, indent=1))
    (results_dir / "cells.json").write_text(json.dumps(results, indent=1))
    print("wrote results/cells.json and results/env.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
