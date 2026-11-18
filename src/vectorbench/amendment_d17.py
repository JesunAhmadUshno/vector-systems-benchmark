"""Amendment D17: pgvector per-query recall capture + D14 intervals.

Mirrors run_pgvector through the repo own run_cell with a reps=1
study, captures per-query recall from repetition 1 for all nine
pgvector recall cells, and computes D14-method bootstrap intervals
(amendment_d14.bootstrap_ci, 10,000 resamples, seed 20261117).
A cell interval is reported only if the fresh aggregate reproduces
the committed results_pg/cells.json recall@10 within 0.001.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .amendment_d14 import bootstrap_ci, per_query_recall
from .run_benchmark import (
    MAIN_CELLS,
    Study,
    apply_churn_to_study,
    churn_setup,
    insert_payloads,
    payloads_for,
    prepare,
    run_cell,
    tune_breadth,
)

TOL = 0.001


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--pg-conninfo", required=True)
    ap.add_argument("--committed", default="results_pg/cells.json")
    args = ap.parse_args()

    bundle = prepare(Path(args.data_dir))
    study = Study(bundle, n_queries=300, reps=1)

    committed = {}
    d = json.loads(Path(args.committed).read_text())
    for sec in ("cells", "trap", "churn"):
        for c in d.get(sec, []):
            if c.get("backend") == "pgvector":
                committed[c["cell"]] = c["recall10"]

    entries = {}

    def record(label, cell, study_ref, spec):
        gt = study_ref.ground_truth(spec)
        pq = per_query_recall(cell["_returned"], gt)
        entry = {
            "cell": label,
            "committed_recall10": committed.get(label),
            "fresh_recall10_rep1": cell["recall10"],
            "per_query_recall": [round(float(x), 6) for x in pq],
        }
        if committed.get(label) is not None and abs(cell["recall10"] - committed[label]) <= TOL:
            entry["interval"] = bootstrap_ci(pq)
        else:
            entry["interval"] = None
            entry["note"] = (
                "fresh aggregate does not reproduce the committed "
                "recall@10 within 0.001; interval not reported "
                "(D14 validation rule)"
            )
        entries[label] = entry
        print(label, cell["recall10"], "committed", committed.get(label), flush=True)

    from .adapters.pgvector_adapter import PgvectorAdapter

    ad = PgvectorAdapter(conninfo=args.pg_conninfo, dim=study.dim)
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks, with_row=False))
    ad.conn.execute("ANALYZE chunks")  # D17 addendum 2: environment of record
    ad.set_mode(iterative=True)
    tuning = tune_breadth(ad, study)
    print("tuning:", tuning, flush=True)
    for name in MAIN_CELLS:
        spec, sel = study.filters[name]
        cell = run_cell(ad, study, name, spec, sel)
        record(name, cell, study, spec)
    ad.set_mode(iterative=False)
    ad.set_breadth(40)
    for name in ("tenant_t2", "tenant_t5"):
        spec, sel = study.filters[name]
        cell = run_cell(ad, study, f"trap_{name}", spec, sel)
        record(f"trap_{name}", cell, study, spec)
    ad.set_mode(iterative=True)
    ad.set_breadth(tuning["chosen"])
    delete_ids, inserts, insert_ids = churn_setup(study)
    ad.delete(delete_ids)
    ad.insert([i["id"] for i in inserts], study.vec_by_id[insert_ids], insert_payloads(inserts))
    apply_churn_to_study(study, delete_ids, inserts)
    for name in ("none", "tenant_t5"):
        spec, sel = study.filters[name]
        cell = run_cell(ad, study, f"post_churn_{name}", spec, sel)
        record(f"post_churn_{name}", cell, study, spec)
    ad.close()

    out = {
        "amendment": "D17",
        "method": "per-query bootstrap, 10000 resamples, seed 20261117, "
                  "percentile 95 percent (amendment_d14.bootstrap_ci); "
                  "per-query recall from repetition 1",
        "tuning": tuning,
        "cells": entries,
    }
    Path(args.results_dir, "amendment_d17.json").write_text(json.dumps(out, indent=1))
    for label, e in entries.items():
        iv = e["interval"]["ci95_percentile"] if e["interval"] else "NO INTERVAL"
        print(label, e["fresh_recall10_rep1"], iv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
