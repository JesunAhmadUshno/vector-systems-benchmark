"""Amendment D14: per-cell recall@10 uncertainty intervals.

Registered in DECISIONS.md (D14) on 2026-11-17 BEFORE this code ran.

RESULTS.md states recall carries no interval because per-query values
were not saved. This amendment adds per-query bootstrap intervals
(10,000 resamples, seed 20261117, percentile 95 percent) for the
headline cells:

- FAISS: per-query recall re-derived by re-running the FAISS cells
  with the repo harness at the committed frozen breadth (40) on the
  cached corpus artifacts in data/. Validation rule from the
  registration: each re-derived aggregate must reproduce the committed
  results/cells.json recall@10 within 0.001, or the cell's interval
  is not reported.
- Qdrant (embedded): every committed cell is exactly 1.000, which
  forces every per-query value to 1.0; interval is [1.000, 1.000].
- pgvector: per-query values were not saved and PostgreSQL is
  unavailable here. Cells at exactly 1.000 get the degenerate
  interval; other cells are recorded as not computable from the
  committed records, with a supplementary slot-level Wilson interval
  on total hits, labelled as narrower than a per-query interval.

Output: results/amendment_d14.json (path set by --out).
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

from .run_benchmark import (
    K, MAIN_CELLS, Study, apply_churn_to_study, churn_setup,
    insert_payloads, payloads_for, prepare,
)
from .metrics import recall_at_k

BOOT_SEED = 20261117
BOOT_N = 10_000
TOL = 0.001


def bootstrap_ci(values: np.ndarray) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    n = len(values)
    means = np.empty(BOOT_N)
    for i in range(BOOT_N):
        idx = rng.integers(0, n, n)
        means[i] = values[idx].mean()
    return {
        "n_queries": int(n),
        "point": round(float(values.mean()), 6),
        "bootstrap_mean": round(float(means.mean()), 6),
        "ci95_percentile": [round(float(np.percentile(means, 2.5)), 6),
                            round(float(np.percentile(means, 97.5)), 6)],
    }


def wilson(hits: int, total: int, z: float = 1.959964) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    p = hits / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def per_query_recall(returned, gt):
    out = []
    for ret, g in zip(returned, gt):
        out.append(len(set(list(ret)[:K]) & set(list(g)[:K])) / K)
    return np.array(out, dtype=np.float64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--committed", default="results/cells.json")
    ap.add_argument("--out", default="results/amendment_d14.json")
    args = ap.parse_args()

    committed = json.loads(Path(args.committed).read_text())
    committed_cells = {}
    for section in ("cells", "churn", "trap"):
        for c in committed.get(section, []):
            committed_cells[(c["backend"], c["arm"], c["cell"])] = c

    bundle = prepare(Path(args.data_dir))
    out = {
        "registered_in": "DECISIONS.md D14 (2026-11-17, before this run)",
        "status": "post-registration amendment; no verdict changes",
        "method": "per-query bootstrap, 10000 resamples, seed 20261117, "
                  "percentile 95 percent interval",
        "cells": {},
    }

    # ---- FAISS: re-derive per-query recall -------------------------------
    from .adapters.faiss_adapter import FaissAdapter

    study = Study(bundle, n_queries=300, reps=3)
    ad = FaissAdapter(dim=study.dim)
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks))
    ad.set_breadth(40)  # committed frozen breadth (tuning chose 40)

    faiss_entries = {}
    pre = {}
    for cell_name in MAIN_CELLS:
        spec, _sel = study.filters[cell_name]
        gt = study.ground_truth(spec)
        returned = [ad.search(q, K, spec) for q in study.queries]
        pq = per_query_recall(returned, gt)
        ref = committed_cells[("faiss", "main", cell_name)]
        agg = float(pq.mean())
        faiss_entries[cell_name] = {
            "backend": "faiss", "arm": "main", "cell": cell_name,
            "source": "re-derived per-query recall (repo harness, cached "
                      "corpus artifacts, frozen breadth 40)",
            "committed_recall10": ref["recall10"],
            "rederived_recall10": round(agg, 6),
            "aggregate_matches_within_0.001": abs(agg - ref["recall10"]) <= TOL,
            "per_query_recall10": [round(float(x), 4) for x in pq],
        }
        if abs(agg - ref["recall10"]) <= TOL:
            faiss_entries[cell_name]["interval"] = bootstrap_ci(pq)
        pre[cell_name] = ref["recall10"]
        print("faiss main", cell_name, agg, "committed", ref["recall10"], flush=True)

    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts],
              study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    deleted = set(delete_ids)
    for arm, bookkeeping in [("raw", False), ("bookkeeping", True)]:
        ad.bookkeeping = bookkeeping
        for cell_name in ["none", "tenant_t5"]:
            label = f"post_churn_{cell_name}"
            spec, _sel = study.filters[cell_name]
            gt = study.ground_truth(spec)
            returned = [ad.search(q, K, spec) for q in study.queries]
            pq = per_query_recall(returned, gt)
            ref = committed_cells[("faiss", arm, label)]
            agg = float(pq.mean())
            entry = {
                "backend": "faiss", "arm": arm, "cell": label,
                "source": "re-derived per-query recall (repo harness, "
                          "cached corpus artifacts, frozen breadth 40)",
                "committed_recall10": ref["recall10"],
                "rederived_recall10": round(agg, 6),
                "aggregate_matches_within_0.001": abs(agg - ref["recall10"]) <= TOL,
                "per_query_recall10": [round(float(x), 4) for x in pq],
            }
            if abs(agg - ref["recall10"]) <= TOL:
                entry["interval"] = bootstrap_ci(pq)
            # Per-query stale share (share of the query's returned slots
            # holding a deleted id), bootstrap alongside.
            stale_pq = np.array([
                (sum(1 for r in ret if r in deleted) / len(ret)) if ret else 0.0
                for ret in returned
            ], dtype=np.float64)
            entry["stale_rate_committed"] = ref["stale_rate"]
            entry["stale_rate_rederived_slot_level"] = round(
                float(sum(1 for ret in returned for r in ret if r in deleted)
                      / max(1, sum(len(ret) for ret in returned))), 6)
            entry["stale_share_per_query_bootstrap"] = bootstrap_ci(stale_pq)
            faiss_entries[label + ":" + arm] = entry
            print("faiss churn", arm, label, agg, "committed", ref["recall10"], flush=True)
    ad.close()
    out["cells"]["faiss"] = faiss_entries

    # ---- Qdrant embedded + pgvector: from the committed record -----------
    for backend in ("qdrant", "pgvector"):
        entries = {}
        for (b, arm, cell), ref in sorted(committed_cells.items()):
            if b != backend:
                continue
            key = f"{cell}:{arm}"
            rec = ref["recall10"]
            if rec == 1.0:
                entries[key] = {
                    "backend": backend, "arm": arm, "cell": cell,
                    "source": "committed aggregate (results/cells.json)",
                    "committed_recall10": rec,
                    "interval": {"n_queries": ref["n_queries"], "point": 1.0,
                                 "ci95_percentile": [1.0, 1.0]},
                    "note": "Committed recall is exactly 1.000 and per-query "
                            "recall@10 cannot exceed 1.0, so every per-query "
                            "value is 1.0; the bootstrap interval is "
                            "degenerate.",
                }
            elif backend == "qdrant":
                entries[key] = {
                    "backend": backend, "arm": arm, "cell": cell,
                    "committed_recall10": rec,
                    "interval": None,
                    "note": "No committed Qdrant cell is below 1.000; this "
                            "branch is unreachable on the committed record.",
                }
            else:
                hits = int(round(rec * ref["n_queries"] * K))
                total = ref["n_queries"] * K
                entries[key] = {
                    "backend": backend, "arm": arm, "cell": cell,
                    "source": "committed aggregate (results/cells.json)",
                    "committed_recall10": rec,
                    "interval": None,
                    "note": "Per-query values were not saved and PostgreSQL "
                            "is unavailable in this environment, so no "
                            "per-query bootstrap interval can be computed "
                            "from the committed records for this cell.",
                    "supplementary_slot_level_wilson_on_total_hits": {
                        "hits": hits, "slots": total,
                        "ci95": wilson(hits, total),
                        "caveat": "Treats returned slots within a query as "
                                  "independent; narrower than a per-query "
                                  "interval would be. Not a per-query "
                                  "interval.",
                    },
                }
            print(backend, key, rec, flush=True)
        out["cells"][backend] = entries

    Path(args.out).write_text(json.dumps(out, indent=1))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
