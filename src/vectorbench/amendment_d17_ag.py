"""D17 addendum 3: dedicated article_group execution.

Mirrors amendment_d17.py exactly (same build, the addendum 2
ANALYZE step, same breadth tuning, the repo own run_cell,
repetition-1 per-query capture, the D14 bootstrap unchanged)
but executes only the article_group main cell, under the
execution 3 environment of record (pgvector 0.8.0 container).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .amendment_d14 import bootstrap_ci, per_query_recall
from .run_benchmark import Study, payloads_for, prepare, run_cell, tune_breadth

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

    from .adapters.pgvector_adapter import PgvectorAdapter

    ad = PgvectorAdapter(conninfo=args.pg_conninfo, dim=study.dim)
    ids = [c["id"] for c in study.chunks]
    ad.build(ids, study.vec_by_id[ids], payloads_for(study.chunks, with_row=False))
    ad.conn.execute("ANALYZE chunks")  # D17 addendum 2: environment of record
    ad.set_mode(iterative=True)
    tuning = tune_breadth(ad, study)
    print("tuning:", tuning, flush=True)

    spec, sel = study.filters["article_group"]
    cell = run_cell(ad, study, "article_group", spec, sel)
    gt = study.ground_truth(spec)
    pq = per_query_recall(cell["_returned"], gt)
    entry = {
        "cell": "article_group",
        "committed_recall10": committed.get("article_group"),
        "fresh_recall10_rep1": cell["recall10"],
        "per_query_recall": [round(float(x), 6) for x in pq],
    }
    if committed.get("article_group") is not None and abs(
        cell["recall10"] - committed["article_group"]
    ) <= TOL:
        entry["interval"] = bootstrap_ci(pq)
    else:
        entry["interval"] = None
        entry["note"] = (
            "fresh aggregate does not reproduce the committed "
            "recall@10 within 0.001; interval not reported "
            "(D14 validation rule)"
        )
    print("article_group", cell["recall10"], "committed",
          committed.get("article_group"), flush=True)
    ad.close()

    out = {
        "amendment": "D17 addendum 3",
        "method": "per-query bootstrap, 10000 resamples, seed 20261117, "
                  "percentile 95 percent (amendment_d14.bootstrap_ci); "
                  "per-query recall from repetition 1; article_group "
                  "cell only",
        "environment": "pgvector/pgvector:0.8.0-pg16 (pgvector 0.8.0), "
                       "ANALYZE after build (D17 execution 3 conditions)",
        "tuning": tuning,
        "cells": {"article_group": entry},
    }
    Path(args.results_dir,
         "amendment_d17_pg080_analyzed_articlegroup.json").write_text(
        json.dumps(out, indent=1))
    iv = entry["interval"]["ci95_percentile"] if entry["interval"] else "NO INTERVAL"
    print("article_group", entry["fresh_recall10_rep1"], iv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
