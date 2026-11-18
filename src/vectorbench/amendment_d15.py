"""Amendment D15: Qdrant server-mode rerun at the matched protocol.

Registered in DECISIONS.md (D15) on 2026-11-17 BEFORE this code ran
(and before the server binary was downloaded).

The committed Qdrant numbers come from embedded local mode (exact
brute force by construction) at 100 queries x 2 repetitions (D10).
This amendment reruns the Qdrant arms against the official Qdrant
server binary on localhost, at the matched protocol of the other
systems (300 queries x 3 repetitions), with the repo adapter's
collection configuration unchanged (dense cosine, HNSW m = 32,
ef_construct = 200, sparse BM25 vector, payload indexes before
ingestion). Breadth is tuned with the repo ladder rule and frozen.
Cells: the five main cells, then the registered churn step and the
two post-churn cells with stale rate. Per-query recall@10 is saved
for every cell, with per-query bootstrap intervals as in D14.

Output: results/amendment_d15.json (path set by --out).
"""
import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client import models as qm

from .adapters.qdrant_adapter import COLLECTION, QdrantAdapter
from .amendment_d14 import bootstrap_ci, per_query_recall
from .metrics import mean_returned, percentiles_ms, recall_at_k, shortfall_rate, stale_rate
from .run_benchmark import (
    K, MAIN_CELLS, Study, apply_churn_to_study, churn_setup,
    insert_payloads, payloads_for, prepare, tune_breadth,
)


class ServerQdrantAdapter(QdrantAdapter):
    """QdrantAdapter with the client pointed at a running server.

    Everything else (collection config, payload indexes, point
    construction, filter and search-params logic) is inherited or
    copied verbatim from QdrantAdapter.__init__.
    """

    def __init__(self, url: str, dim: int, bm25=None, m: int = 32, ef_construct: int = 200):
        self.client = QdrantClient(url=url, timeout=300)
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
        self.client.create_payload_index(COLLECTION, "tenant", qm.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(COLLECTION, "article", qm.PayloadSchemaType.KEYWORD)


def run_cell_server(adapter, study, label, filter_spec, selectivity):
    gt = study.ground_truth(filter_spec)
    recall_runs = []
    lat_runs = []
    first_returned = None
    first_pq = None
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
            first_pq = per_query_recall(returned, gt)
    median_rep = int(np.argsort([sum(l) for l in lat_runs])[len(lat_runs) // 2])
    pct = percentiles_ms(lat_runs[median_rep])
    return {
        "cell": label,
        "filter": repr(filter_spec),
        "selectivity": selectivity,
        "n_queries": len(study.query_ids),
        "reps": study.reps,
        "recall10": recall_runs[0],
        "recall_runs": recall_runs,
        "shortfall_rate": shortfall_rate(first_returned, K),
        "mean_returned": mean_returned(first_returned),
        "p50_ms": pct["p50"],
        "p95_ms": pct["p95"],
        "per_query_recall10": [round(float(x), 4) for x in first_pq],
        "interval_per_query_bootstrap": bootstrap_ci(first_pq),
        "_returned": first_returned,
    }


def public(cell):
    return {k: v for k, v in cell.items() if not k.startswith("_")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--committed", default="results/cells.json")
    ap.add_argument("--out", default="results/amendment_d15.json")
    ap.add_argument("--url", default="http://localhost:6333")
    ap.add_argument("--scratch", default=str(Path.home() / "workspace/gap-closure/qdrant-server-scratch"))
    args = ap.parse_args()

    committed = json.loads(Path(args.committed).read_text())
    committed_q = {}
    for section in ("cells", "churn"):
        for c in committed.get(section, []):
            if c["backend"] == "qdrant":
                committed_q[(c["arm"], c["cell"])] = c

    with urllib.request.urlopen(args.url + "/", timeout=10) as resp:
        server_info = json.loads(resp.read().decode())

    scratch = Path(args.scratch)
    musl_tar = scratch / "qdrant-musl.tar.gz"
    gnu_tar = scratch / "qdrant.tar.gz"
    provenance = {
        "server_version_reported_by_server": server_info.get("version"),
        "server_commit_reported_by_server": server_info.get("commit"),
        "release": "v1.20.2 (latest official release on 2026-11-17)",
        "binary_used": {
            "asset": "qdrant-x86_64-unknown-linux-musl.tar.gz",
            "url": "https://github.com/qdrant/qdrant/releases/download/"
                   "v1.20.2/qdrant-x86_64-unknown-linux-musl.tar.gz",
            "sha256": hashlib.sha256(musl_tar.read_bytes()).hexdigest()
            if musl_tar.exists() else "file not found in scratch",
        },
        "binary_not_used": {
            "asset": "qdrant-x86_64-unknown-linux-gnu.tar.gz",
            "url": "https://github.com/qdrant/qdrant/releases/download/"
                   "v1.20.2/qdrant-x86_64-unknown-linux-gnu.tar.gz",
            "sha256": hashlib.sha256(gnu_tar.read_bytes()).hexdigest()
            if gnu_tar.exists() else "file not found in scratch",
            "reason": "Requires GLIBC_2.43; this VM has GLIBC 2.39, so the "
                      "gnu build does not start here. The musl build of "
                      "the same official release is statically linked "
                      "and reports the same version (qdrant 1.20.2).",
        },
        "storage": "scratch directory outside the repo "
                   "(~/workspace/gap-closure/qdrant-server-scratch/storage)",
        "client": "qdrant-client (repo environment)",
    }

    bundle = prepare(Path(args.data_dir))
    study = Study(bundle, n_queries=300, reps=3)

    out = {
        "registered_in": "DECISIONS.md D15 (2026-11-17, before this run)",
        "status": "post-registration amendment; H3 verdict unchanged "
                  "(relabelling is the study owner's decision)",
        "protocol": "300 queries x 3 repetitions (matched to FAISS and "
                    "pgvector); per-query recall saved; bootstrap as D14",
        "server": provenance,
        "cells": [],
        "churn": [],
    }

    ad = ServerQdrantAdapter(url=args.url, dim=study.dim, bm25=bundle["bm25"])
    ids = [c["id"] for c in study.chunks]
    t0 = time.time()
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
    out["ingest_seconds"] = round(time.time() - t0, 1)
    print(f"ingested {len(ids)} points in {out['ingest_seconds']}s", flush=True)

    tuning = tune_breadth(ad, study)
    out["tuning"] = {"ladder": tuning["ladder"], "chosen": tuning["chosen"],
                     "committed_embedded_chosen": 40}
    print("tuning:", tuning, flush=True)

    pre = {}
    for cell_name in MAIN_CELLS:
        spec, sel = study.filters[cell_name]
        cell = run_cell_server(ad, study, cell_name, spec, sel)
        cell["backend"] = "qdrant"
        cell["arm"] = "server"
        ref = committed_q[("main", cell_name)]
        cell["committed_embedded_recall10"] = ref["recall10"]
        cell["committed_embedded_shortfall_rate"] = ref["shortfall_rate"]
        cell["committed_embedded_p50_ms"] = ref["p50_ms"]
        cell["committed_embedded_p95_ms"] = ref["p95_ms"]
        out["cells"].append(public(cell))
        pre[cell_name] = cell["recall10"]
        print("server main", cell_name, cell["recall10"],
              "shortfall", cell["shortfall_rate"],
              "p95", round(cell["p95_ms"], 2), flush=True)

    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts],
              study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    for cell_name in ["none", "tenant_t5"]:
        label = f"post_churn_{cell_name}"
        spec, sel = study.filters[cell_name]
        cell = run_cell_server(ad, study, label, spec, sel)
        cell["backend"] = "qdrant"
        cell["arm"] = "server"
        cell["stale_rate"] = stale_rate(cell["_returned"], delete_ids)
        cell["pre_churn_recall10"] = pre[cell_name]
        ref = committed_q[("native", label)]
        cell["committed_embedded_recall10"] = ref["recall10"]
        cell["committed_embedded_stale_rate"] = ref["stale_rate"]
        out["churn"].append(public(cell))
        print("server churn", label, cell["recall10"],
              "stale", cell["stale_rate"], flush=True)
    ad.close()

    main_by_cell = {c["cell"]: c for c in out["cells"]}
    churn_by_cell = {c["cell"]: c for c in out["churn"]}
    tight = main_by_cell["tenant_t5"]
    out["headline_readings"] = {
        "unfiltered_recall_1.000": {
            "committed_embedded": 1.0,
            "server": main_by_cell["none"]["recall10"],
            "reading_holds_exactly": main_by_cell["none"]["recall10"] == 1.0,
        },
        "hold_at_about_1_percent_selectivity": {
            "committed_embedded_tight_recall10": 1.0,
            "committed_embedded_tight_shortfall": 0.0,
            "server_tight_recall10": tight["recall10"],
            "server_tight_shortfall": tight["shortfall_rate"],
            "h3_falsification_rule": "tight recall below 0.90 or any "
                                     "shortfall falsifies H3",
            "h3_rule_triggered": bool(tight["recall10"] < 0.90
                                      or tight["shortfall_rate"] > 0),
        },
        "zero_stale_after_churn": {
            "committed_embedded_stale_rates": {
                k: v["committed_embedded_stale_rate"]
                for k, v in churn_by_cell.items()},
            "server_stale_rates": {
                k: v["stale_rate"] for k, v in churn_by_cell.items()},
            "reading_holds": all(v["stale_rate"] == 0.0
                                 for v in churn_by_cell.values()),
        },
    }

    Path(args.out).write_text(json.dumps(out, indent=1))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
