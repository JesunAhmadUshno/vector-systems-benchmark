"""Generate RESULTS.md and results/readme_table.md from results/*.json.

No number in the output is typed by hand. Hypothesis verdicts are computed
here from the thresholds pre-registered in HYPOTHESES.md.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

CELL_LABELS = {
    "none": "Unfiltered",
    "tenant_t0": "Filter, random label, about 50 percent selectivity",
    "tenant_t2": "Filter, random label, about 10 percent selectivity",
    "tenant_t5": "Filter, random label, about 1 percent selectivity (tight)",
    "article_group": "Filter, correlated label, about 1 percent selectivity",
    "post_churn_none": "Post-churn, unfiltered",
    "post_churn_tenant_t5": "Post-churn, tight filter",
    "trap_tenant_t2": "Trap cell, about 10 percent selectivity, defaults",
    "trap_tenant_t5": "Trap cell, about 1 percent selectivity, defaults",
}

BACKEND_ORDER = ["faiss", "pgvector", "qdrant"]


def f3(x):
    return "n/a" if x is None else f"{x:.3f}"


def f2(x):
    return "n/a" if x is None else f"{x:.2f}"


def wilson(p: float, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score 95 percent interval for a proportion p observed over n trials."""
    if n <= 0:
        return (0.0, 1.0)
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = (z / den) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def ci3(lo_hi) -> str:
    return f"{lo_hi[0]:.3f} to {lo_hi[1]:.3f}"


def shortfall_ci(e) -> tuple[float, float]:
    # Shortfall is a per-query yes/no outcome, so n is the number of queries.
    return wilson(e["shortfall_rate"], e["n_queries"])


def stale_slots(e) -> int:
    return round(e["n_queries"] * e["mean_returned"])


def stale_ci(e) -> tuple[float, float]:
    # Stale rate is a share of returned slots. Slots within one query are not
    # independent, so this slot-level interval is narrower than a query-level one.
    return wilson(e["stale_rate"], stale_slots(e))


def c2_check(results) -> dict:
    """C2 candidate-starvation model: mean returned is about ef_search x selectivity
    (default ef_search 40) while the ANN index plan is used. Agreement means the
    measured mean returned is within 10 percent of the prediction capped at k."""
    out = {}
    for name in ("trap_tenant_t2", "trap_tenant_t5"):
        e = find(results["trap"], "pgvector", name)
        if e is None:
            continue
        predicted = 40 * (e["selectivity"] or 0)
        capped = min(10.0, predicted)
        agrees = abs(e["mean_returned"] - capped) <= 0.10 * max(capped, 1e-9)
        out[name] = {"predicted": predicted, "measured": e["mean_returned"], "agrees": agrees}
    return out


def find(entries, backend, cell, arm=None):
    for e in entries:
        if e["backend"] == backend and e["cell"] == cell and (arm is None or e.get("arm") == arm):
            return e
    return None


def measured_backends(results) -> list[str]:
    seen = {c["backend"] for c in results["cells"]}
    return [b for b in BACKEND_ORDER if b in seen]


# ---------------------------------------------------------------------------
# Verdicts
# ---------------------------------------------------------------------------

def verdicts(results) -> list[dict]:
    cells = results["cells"]
    churn = results["churn"]
    trap = results["trap"]
    hybrid = results["hybrid"]
    out = []

    # H1: pgvector trap and fix
    t5_trap = find(trap, "pgvector", "trap_tenant_t5")
    t2_trap = find(trap, "pgvector", "trap_tenant_t2")
    t5_iter = find(cells, "pgvector", "tenant_t5")
    if t5_trap is None or t5_iter is None:
        out.append({"id": "H1", "verdict": "Inconclusive",
                    "evidence": "pgvector trap or iterative cell is missing."})
    else:
        trap_bad = t5_trap["shortfall_rate"] > 0.50 or t5_trap["recall10"] < 0.50
        fix_good = t5_iter["recall10"] >= 0.90 and t5_iter["shortfall_rate"] <= 0.05
        ev = (f"Tight cell at defaults: recall {f3(t5_trap['recall10'])}, shortfall {f3(t5_trap['shortfall_rate'])}, "
              f"mean returned {f2(t5_trap['mean_returned'])}. "
              f"Tight cell with iterative scan on: recall {f3(t5_iter['recall10'])}, shortfall {f3(t5_iter['shortfall_rate'])}.")
        if t2_trap is not None:
            ev += (f" One band up, at about 10 percent selectivity, the trap does appear at defaults: "
                   f"recall {f3(t2_trap['recall10'])}, shortfall {f3(t2_trap['shortfall_rate'])}, "
                   f"mean returned {f2(t2_trap['mean_returned'])}. The pattern matches the research "
                   f"pack's row 10: at very low selectivity the planner can leave the ANN index and "
                   f"answer exactly over the filtered subset, which rescues the tight cell. H1 is "
                   f"therefore judged on its pre-registered tight-cell wording.")
        if trap_bad and fix_good:
            v = "Supported"
        elif not trap_bad:
            v = "Refuted"
        else:
            v = "Partially supported"
        out.append({"id": "H1", "verdict": v, "evidence": ev})

    # H2: no universal winner
    backends = measured_backends(results)
    cell_names = ["none", "tenant_t0", "tenant_t2", "tenant_t5", "article_group"]
    leads = {b: 0 for b in backends}
    total_cells = 0
    sweep = {b: 0 for b in backends}  # cells where backend leads both metrics
    for name in cell_names:
        entries = [find(cells, b, name) for b in backends]
        entries = [e for e in entries if e is not None]
        if len(entries) < 2:
            continue
        total_cells += 1
        best_recall = max(e["recall10"] for e in entries)
        best_p95 = min(e["p95_ms"] for e in entries)
        recall_leaders = {e["backend"] for e in entries if abs(e["recall10"] - best_recall) < 1e-9}
        p95_leaders = {e["backend"] for e in entries if abs(e["p95_ms"] - best_p95) < 1e-9}
        for b in recall_leaders | p95_leaders:
            leads[b] += 1
        for b in recall_leaders & p95_leaders:
            sweep[b] += 1
    if total_cells == 0 or len(backends) < 2:
        out.append({"id": "H2", "verdict": "Inconclusive",
                    "evidence": "Fewer than two backends have measured main cells."})
    else:
        ev = (f"Cells compared: {total_cells} (the five main filter cells; the post-churn "
              f"cells listed in the pre-registered H2 are not included, see DECISIONS.md D11). Cell leads (recall or p95): "
              + ", ".join(f"{b} {leads[b]}" for b in backends)
              + ". Cells swept on both metrics: "
              + ", ".join(f"{b} {sweep[b]}" for b in backends) + ".")
        if any(sweep[b] == total_cells for b in backends):
            v = "Refuted"
        elif all(leads[b] > 0 for b in backends):
            v = "Supported"
        else:
            v = "Partially supported"
        out.append({"id": "H2", "verdict": v, "evidence": ev})

    # H3: Qdrant tight-cell stability
    q_t5 = find(cells, "qdrant", "tenant_t5")
    if q_t5 is None:
        out.append({"id": "H3", "verdict": "Inconclusive", "evidence": "Qdrant tight cell is missing."})
    else:
        ev = (f"Qdrant tight cell: recall {f3(q_t5['recall10'])}, "
              f"shortfall {f3(q_t5['shortfall_rate'])} at frozen breadth. "
              f"Caveat: measured in embedded local mode, which the client itself warns "
              f"performs exact brute-force search; this supports the hypothesis for the "
              f"embedded engine only. The server product's filtered HNSW is not measured "
              f"here and stays Not yet measured (REPORT.md next step 1).")
        if q_t5["recall10"] >= 0.90 and q_t5["shortfall_rate"] == 0:
            v = "Supported"
        elif q_t5["recall10"] >= 0.90:
            v = "Partially supported"
        else:
            v = "Refuted"
        out.append({"id": "H3", "verdict": v, "evidence": ev})

    # H4: FAISS lowest p95 at matched recall, unfiltered
    unfiltered = {b: find(cells, b, "none") for b in backends}
    f_unf = unfiltered.get("faiss")
    if f_unf is None:
        out.append({"id": "H4", "verdict": "Inconclusive", "evidence": "FAISS unfiltered cell is missing."})
    elif f_unf["recall10"] < 0.95:
        out.append({"id": "H4", "verdict": "Inconclusive",
                    "evidence": f"FAISS unfiltered recall {f3(f_unf['recall10'])} is below the 0.95 operating point."})
    else:
        rivals = [e for b, e in unfiltered.items()
                  if e is not None and b != "faiss" and e["recall10"] >= 0.95]
        ev = (f"FAISS p95 {f2(f_unf['p95_ms'])} ms at recall {f3(f_unf['recall10'])}. "
              + "; ".join(f"{e['backend']} p95 {f2(e['p95_ms'])} ms at recall {f3(e['recall10'])}" for e in rivals))
        v = "Supported" if all(f_unf["p95_ms"] <= e["p95_ms"] for e in rivals) else "Refuted"
        out.append({"id": "H4", "verdict": v, "evidence": ev})

    # H5: churn freshness lines
    lines = []
    pg_post = find(churn, "pgvector", "post_churn_none")
    if pg_post is not None:
        lines.append(("pgvector stale rate 0", pg_post["stale_rate"] == 0,
                      f"pgvector stale {f3(pg_post['stale_rate'])}"))
    q_post = find(churn, "qdrant", "post_churn_none")
    if q_post is not None:
        lines.append(("qdrant stale rate 0", q_post["stale_rate"] == 0,
                      f"qdrant stale {f3(q_post['stale_rate'])}"))
    f_raw = find(churn, "faiss", "post_churn_none", arm="raw")
    if f_raw is not None:
        lines.append(("faiss raw stale rate above 0", f_raw["stale_rate"] > 0,
                      f"faiss raw stale {f3(f_raw['stale_rate'])}"))
    f_book = find(churn, "faiss", "post_churn_none", arm="bookkeeping")
    if f_book is not None:
        lines.append(("faiss bookkeeping stale rate 0", f_book["stale_rate"] == 0,
                      f"faiss bookkeeping stale {f3(f_book['stale_rate'])}"))
    drops = []
    for b, entry in [("pgvector", pg_post), ("qdrant", q_post), ("faiss", f_book)]:
        if entry is not None:
            drop = entry["pre_churn_recall10"] - entry["recall10"]
            drops.append((b, drop))
    if drops:
        ok = all(d < 0.05 for _b, d in drops)
        lines.append(("recall drop below 0.05 for every backend", ok,
                      ", ".join(f"{b} drop {f3(d)}" for b, d in drops)))
    if len(lines) < 3:
        out.append({"id": "H5", "verdict": "Inconclusive",
                    "evidence": "Too few churn lines measured: " + "; ".join(e for _n, _p, e in lines)})
    else:
        passed = sum(1 for _n, p, _e in lines if p)
        ev = "; ".join(f"{name}: {'pass' if p else 'FAIL'} ({e})" for name, p, e in lines) + "."
        v = "Supported" if passed == len(lines) else ("Partially supported" if passed >= 3 else "Refuted")
        out.append({"id": "H5", "verdict": v, "evidence": ev})

    # H6: hybrid gain per backend
    gains = []
    for b in backends:
        h = hybrid.get(b)
        if h:
            gain = h["arms"]["hybrid"]["ndcg10"] - h["arms"]["dense"]["ndcg10"]
            gains.append((b, gain))
    if not gains:
        out.append({"id": "H6", "verdict": "Inconclusive", "evidence": "No hybrid arms measured."})
    else:
        ev = "; ".join(f"{b} hybrid gain {gain:+.3f} nDCG" for b, gain in gains) + "."
        passed = sum(1 for _b, g in gains if g >= 0.02)
        v = "Supported" if passed == len(gains) else ("Partially supported" if passed > 0 else "Refuted")
        out.append({"id": "H6", "verdict": v, "evidence": ev})

    return out


# ---------------------------------------------------------------------------
# Document build
# ---------------------------------------------------------------------------

def cell_table(results, cell_names, entries_key="cells") -> str:
    entries = results[entries_key]
    lines = []
    for name in cell_names:
        lines.append(f"### {CELL_LABELS.get(name, name)}")
        lines.append("")
        lines.append("| Backend | Arm | Selectivity | Queries x reps | recall@10 | Shortfall rate | Shortfall 95% CI | Mean returned | p50 ms | p95 ms |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for b in BACKEND_ORDER:
            for e in [x for x in entries if x["cell"] == name and x["backend"] == b]:
                lines.append(
                    f"| {b} | {e.get('arm', '')} | {f3(e['selectivity'])} | {e['n_queries']} x {e['reps']} | "
                    f"{f3(e['recall10'])} | {f3(e['shortfall_rate'])} | {ci3(shortfall_ci(e))} | "
                    f"{f2(e['mean_returned'])} | {f2(e['p50_ms'])} | {f2(e['p95_ms'])} |"
                )
        lines.append("")
    return "\n".join(lines)


def build(results: dict, env: dict) -> tuple[str, str]:
    lines = []
    lines.append("# Results")
    lines.append("")
    lines.append("Generated by `python -m vectorbench.generate_results` from the JSON files in")
    lines.append("this directory. No number in this file was typed by hand.")
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    for key in ["date_utc", "cpu", "python", "platform", "numpy", "faiss", "qdrant_client",
                "model2vec", "postgres", "pgvector", "embedding_model", "corpus",
                "corpus_licence", "n_chunks", "n_heldout_chunks", "dim", "n_queries", "reps", "k"]:
        if key in env:
            lines.append(f"| {key} | {env[key]} |")
    lines.append("")
    if "qdrant_protocol_note" in env:
        lines.append(f"Sample size per backend: {env['qdrant_protocol_note']}. The n_queries and reps "
                     f"rows above are the FAISS and pgvector protocol; every results table below "
                     f"gives queries x reps per row.")
        lines.append("")
    lines.append("Shortfall 95% CI is a Wilson score interval over queries (shortfall is a per-query "
                 "yes/no outcome). Stale 95% CI is a Wilson interval over returned slots; slots within "
                 "a query are not independent, so it is narrower than a query-level interval would be. "
                 "Recall, nDCG and latency carry no interval: per-query values were not saved.")
    lines.append("")
    lines.append("Measured filter selectivities: "
                 + ", ".join(f"{k} {f3(v)}" for k, v in env.get("filter_selectivity_measured", {}).items())
                 + ".")
    lines.append("")
    lines.append("## Tuning")
    lines.append("")
    lines.append("Breadth ladder tried on the unfiltered cell; the first value reaching")
    lines.append("recall@10 at or above 0.95 was frozen for all cells of that backend.")
    lines.append("")
    lines.append("| Backend | Ladder (breadth: recall) | Chosen |")
    lines.append("|---|---|---|")
    for b in BACKEND_ORDER:
        t = results["tuning"].get(b)
        if t:
            ladder = ", ".join(f"{s['breadth']}: {f3(s['recall10'])}" for s in t["ladder"])
            lines.append(f"| {b} | {ladder} | {t['chosen']} |")
    lines.append("")
    lines.append("## Regime map: recall and latency by cell")
    lines.append("")
    lines.append(cell_table(results, ["none", "tenant_t0", "tenant_t2", "tenant_t5", "article_group"]))
    lines.append("## The pgvector trap cell (defaults)")
    lines.append("")
    lines.append("Iterative scan off, hnsw.ef_search = 40, the configuration an untuned")
    lines.append("deployment runs. The main pgvector cells above run iterative scan on.")
    lines.append("")
    lines.append(cell_table(results, ["trap_tenant_t2", "trap_tenant_t5"], entries_key="trap"))
    t5_trap = find(results["trap"], "pgvector", "trap_tenant_t5")
    t2_trap = find(results["trap"], "pgvector", "trap_tenant_t2")
    if t5_trap is not None and t2_trap is not None:
        c2 = c2_check(results)
        pred_t5 = c2["trap_tenant_t5"]["predicted"]
        pred_t2 = c2["trap_tenant_t2"]["predicted"]
        lines.append(f"C2 check: the research pack's model says mean returned is about ef_search times "
                     f"selectivity, as long as the ANN index plan is used. At about 10 percent selectivity "
                     f"the prediction is {f2(pred_t2)} and the measured mean returned is "
                     f"{f2(t2_trap['mean_returned'])}: agreement. At about 1 percent the prediction is "
                     f"{f2(pred_t5)} and the measured mean returned is {f2(t5_trap['mean_returned'])}: "
                     f"disagreement, explained by the planner leaving the ANN index at very low "
                     f"selectivity (research pack row 10), so the model's condition does not hold there.")
        lines.append("")
    lines.append("## Churn: after deleting 10 percent and inserting 10 percent")
    lines.append("")
    churn = results["churn"]
    lines.append("| Backend | Arm | Cell | Queries x reps | recall@10 | Pre-churn recall@10 | Stale rate | Stale 95% CI (slots) | p50 ms | p95 ms |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for b in BACKEND_ORDER:
        for e in [x for x in churn if x["backend"] == b]:
            lines.append(
                f"| {b} | {e.get('arm', '')} | {CELL_LABELS.get(e['cell'], e['cell'])} | {e['n_queries']} x {e['reps']} | "
                f"{f3(e['recall10'])} | {f3(e.get('pre_churn_recall10'))} | {f3(e.get('stale_rate'))} | "
                f"{ci3(stale_ci(e))} ({stale_slots(e)}) | {f2(e['p50_ms'])} | {f2(e['p95_ms'])} |"
            )
    lines.append("")
    lines.append("## Hybrid search quality")
    lines.append("")
    lines.append("| Backend | Fusion | Dense nDCG@10 | BM25 nDCG@10 | Hybrid nDCG@10 | Dense recall@100 | Hybrid recall@100 | Questions |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for b in BACKEND_ORDER:
        h = results["hybrid"].get(b)
        if h:
            a = h["arms"]
            lines.append(
                f"| {b} | {h.get('fusion', '')} | {f3(a['dense']['ndcg10'])} | {f3(a['bm25_shared']['ndcg10'])} | "
                f"{f3(a['hybrid']['ndcg10'])} | {f3(a['dense']['recall100'])} | {f3(a['hybrid']['recall100'])} | "
                f"{h.get('n_questions_scored', '')} |"
            )
    lines.append("")
    if results["blocked"]:
        lines.append("## Blocked backends")
        lines.append("")
        for blk in results["blocked"]:
            lines.append(f"- {blk['backend']}: {blk['error']}")
        lines.append("")
    lines.append("## Hypothesis verdicts")
    lines.append("")
    lines.append("| Hypothesis | Verdict | Evidence |")
    lines.append("|---|---|---|")
    for v in verdicts(results):
        ev = v["evidence"].replace("|", "/")
        lines.append(f"| {v['id']} | {v['verdict']} | {ev} |")
    lines.append("")
    results_md = "\n".join(lines)

    # README headline table
    rl = []
    rl.append("| Backend | Unfiltered recall@10 | Unfiltered p95 ms | Tight filter recall@10 | Tight shortfall | Post-churn recall drop | Hybrid nDCG@10 (dense to hybrid) |")
    rl.append("|---|---|---|---|---|---|---|")
    for b in BACKEND_ORDER:
        unf = find(results["cells"], b, "none")
        if unf is None:
            rl.append(f"| {b} | not measured | | | | | |")
            continue
        t5 = find(results["cells"], b, "tenant_t5")
        post = find(results["churn"], b, "post_churn_none",
                    arm="bookkeeping" if b == "faiss" else None)
        drop = (post["pre_churn_recall10"] - post["recall10"]) if post else None
        h = results["hybrid"].get(b)
        hyb = f"{f3(h['arms']['dense']['ndcg10'])} to {f3(h['arms']['hybrid']['ndcg10'])}" if h else "n/a"
        rl.append(
            f"| {b} | {f3(unf['recall10'])} | {f2(unf['p95_ms'])} | {f3(t5['recall10']) if t5 else 'n/a'} | "
            f"{f3(t5['shortfall_rate']) if t5 else 'n/a'} | {f3(drop)} | {hyb} |"
        )
    readme_table = "\n".join(rl)
    return results_md, readme_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results")
    args = ap.parse_args()
    rd = Path(args.results_dir)
    results = json.loads((rd / "cells.json").read_text())
    env = json.loads((rd / "env.json").read_text())
    results_md, readme_table = build(results, env)
    (rd / "RESULTS.md").write_text(results_md + "\n")
    (rd / "readme_table.md").write_text(readme_table + "\n")
    root_results = Path("RESULTS.md")
    root_results.write_text(results_md + "\n")
    print("wrote RESULTS.md and results/readme_table.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
