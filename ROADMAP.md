# Roadmap: the Deep pass, in evidence order

The Build pass (this repository today) measures the regime map at one
operating point per backend, one churn cycle, and one hybrid
configuration. The Deep pass items below are ordered by how much each
one strengthens or threatens the published verdicts.

1. Qdrant server mode. Rerun the Qdrant cells against the production
   server binary on localhost. This retires the largest named
   limitation: local mode latency, and local mode recall being exact
   by construction instead of measured against the server's HNSW.
2. Matched-recall Pareto curves. Sweep breadth per backend and report
   recall, p95 and p99 at recall 0.90, 0.95 and 0.99 (the pack's
   calculation C4), with 5 runs per setting and 95 percent intervals on
   the means (Miller 2024 style reporting). This converts single
   operating points into curves a reviewer can trust.
3. Churn rates. Repeat the churn cell at 1, 10 and 50 percent churn per
   epoch over several epochs, and add FAISS IVF with remove_ids as the
   FAISS churn baseline the pack names. Measure time for a fresh insert
   to become visible per backend.
4. Selectivity depth. Add 0.1 and 0.01 percent cells, where the trap
   should bite harder, and a second correlated label (publication era of
   the article) to test whether the correlated result generalizes.
5. Hybrid statistics. Paired significance tests for hybrid against dense
   per backend, a second question set (BEIR SciFact, small but standard),
   and an RRF constant sensitivity check (k in 20, 60, 100).
6. Memory and build cost. Process RSS per backend at the frozen
   operating point, and index build time, checked against the pack's C1
   estimate for FAISS.
7. Scale step. 250k and 1M chunk runs to find where the regime
   boundaries move, hardware permitting, with the same harness and
   seeds.
8. Paper write-up. The selectivity by churn by hybrid matrix as a
   reproducibility and measurement paper, working title in the research
   pack, section 7. Only after items 1 to 3 land.
