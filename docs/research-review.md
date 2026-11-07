# Research review

A review of this repository against a doctoral-level research rubric, done
on the committed evidence (results/*.json, RESULTS.md, SPEC.md,
HYPOTHESES.md, METHODS.md, AUDIT.md, DECISIONS.md and the git history).
Each criterion gets a grade, what is strong, what is missing, and either
the fix made in this change or the exact compute or data the remaining gap
needs. The rule applied: every gap that can be closed without a GPU, a paid
API or a long benchmark rerun is closed here.

Grades: A (meets a strong thesis chapter), B (sound, with named gaps),
C (usable, with gaps that limit the claims), D (does not support its claims).

## Summary

| Criterion | Grade | One-line reason |
|---|---|---|
| Research question | A | Specific, falsifiable, stated before code, tied to a real failure (silent shortfall). |
| Hypotheses | A- | Six pre-registered, with thresholds and falsifiers; one undisclosed cell-set deviation, now disclosed (D11). |
| Method and controls | B+ | Same corpus, embeddings, queries and ground truth everywhere; frozen breadth; one deployment-shape confound. |
| Baselines | B | Exact NumPy ground truth and a defaults arm for pgvector; Qdrant server and FAISS IVF baselines missing. |
| Statistics and uncertainty | C+ | Fixed thresholds, no inference; proportion intervals added here; recall, nDCG and latency still have none. |
| Reproducibility | A- | One-command harness, pinned versions, seeds, generated results, a test for the decision logic (added here). |
| Threats to validity | B+ | Named in METHODS.md and AUDIT.md; the H3 local-mode threat undercuts a published verdict. |
| Related work | B | Primary sources for each engine and for filtered ANN; vendor claims labelled; no systematic search record. |
| Limitations | A- | Itemized grade deductions; the C2 headline number was inconsistent and is fixed here. |

Overall: a strong measurement study whose recall and shortfall findings
are well supported, whose latency comparison is a deployed-shape
comparison, and whose Qdrant results speak only for the embedded engine.

## 1. Research question (A)

SPEC.md asks how FAISS, pgvector and Qdrant compare on recall, latency,
filtered recall, freshness and hybrid quality as filter selectivity, churn
and hybrid demand change, and frames the output as a regime map rather
than a ranking. The question is narrow enough to answer on one node and
the harm it targets (a filtered query that silently returns too few
results) is concrete. The git order (838e6da before 4b559bd) shows the
question and hypotheses were fixed before any experiment code.

No gap.

## 2. Hypotheses (A-)

H1 to H6 each give a threshold and a falsification rule, and the verdict
logic in src/vectorbench/generate_results.py applies those thresholds
mechanically. H1 was refuted and is published as refuted, which is the
behaviour pre-registration exists to protect.

Gaps and what was done:

- H2 lists the post-churn cell among its cells, but the code compares
  only the five main filter cells, and the evidence line did not say so.
  Fixed: the H2 evidence now names its cell set, and DECISIONS.md D11
  records the deviation. Whether to recompute H2 with the post-churn
  cells is left open for the study owner; it needs no rerun.
- H3 is labelled Supported, but Qdrant ran in embedded local mode, which
  the client itself warns is exact brute force. The hypothesis is about
  filtered HNSW holding recall without tuning, and an exact scan cannot
  fail that test, so the observation does not test the hypothesis.
  Proposed, not applied: relabel H3 to "Inconclusive (local mode is exact
  by construction)". Changing a published verdict is a decision for the
  study owner; the evidence line already carries the caveat and the site
  shows it next to the verdict. Closing it properly needs item 1 under
  "Remaining gaps".

## 3. Method and controls (B+)

Strong: one corpus, one embedding set, one query set and one exact ground
truth feed every backend; breadth is tuned once on the unfiltered cell and
frozen; the pgvector trap cells deliberately run shipped defaults; the
hybrid arms share the BM25 encoder and the RRF constant.

Gaps:

- Deployment shape confound: FAISS runs in process, pgvector over a Unix
  socket, Qdrant as embedded Python. Latency therefore ranks deployed
  shapes. Disclosed in METHODS.md, README and on every latency view of
  the site. Closing it needs item 1 (Qdrant server) and a FAISS service
  wrapper, both reruns.
- The pgvector hybrid arm uses ts_rank, not the shared BM25, so H6 is not
  encoder-controlled for pgvector. Disclosed. Closing it needs a pgvector
  hybrid arm that fuses the shared BM25 ranking in the application, a
  rerun of the hybrid cell only (about 250 questions, roughly 0.4 s each
  for BM25 top-k, so a few minutes, plus the PostgreSQL setup in AUDIT.md
  and the SQuAD download and embedding cache).
- The 1 percent trap "rescue" is attributed to the planner leaving the
  ANN index, but no EXPLAIN plan was captured. README attributes the mechanism
  to the research pack, and the site now says it is unverified here. Closing it needs one EXPLAIN (ANALYZE)
  per trap cell against the populated vsbench database: seconds of
  compute, but it needs the 58,999-chunk database rebuilt locally.

## 4. Baselines (B)

Exact brute-force NumPy top 10 is the reference for every recall number,
and the harness tests require each adapter to reach recall 1.000 in exact
mode before its approximate numbers count. pgvector has a defaults arm
and an iterative-scan arm, which is the right within-system baseline for
H1.

Gaps (all need reruns, none fixable from committed data):

- Qdrant server mode, the production product (ROADMAP item 1).
- FAISS IVF with remove_ids as the churn baseline the research pack names
  (ROADMAP item 3).
- A filtered-ANN method designed for the problem, such as
  Filtered-DiskANN, cited in README but not run.

## 5. Statistics and uncertainty (C+)

The study reports measured effect sizes against fixed thresholds and
says so in METHODS.md. That is honest, but a reader gets no sense of
sampling error.

Fixed in this change:

- Wilson 95 percent intervals on every shortfall rate (a per-query yes/no
  outcome, so the interval is exact for the recorded n) and on every stale
  rate (over returned slots, with the caveat that slots inside one query
  are not independent, so that interval is too narrow). Both are now
  columns in RESULTS.md and are recomputed live on the site, with a build
  check that the two agree row by row.
- Every results table now shows queries x repetitions per row, so the
  Qdrant rows (100 x 2) are no longer read under the global 300 x 3 in the
  environment table. RESULTS.md also states the per-backend protocol
  under that table.

Remaining, each needing a rerun because per-query values were never
saved (the runner keeps only means and percentiles):

- Bootstrap intervals on recall@10 and on the latency percentiles: rerun
  all cells with per-query recall and per-query latency written to disk.
  At the published protocol that is the full study, dominated by the
  Qdrant local-mode cost the AUDIT records (about a second per query),
  so well over an hour; FAISS alone is minutes.
- A paired test of hybrid against dense (H6): rerun the hybrid cell
  saving per-question nDCG@10 for both arms, then a paired bootstrap or
  Wilcoxon signed-rank test. Minutes per backend.
- p99 latency and matched-recall Pareto curves: sweep the breadth ladder
  (40 to 320) per backend and cell with 5 runs each (ROADMAP item 2).
- Repetitions add no recall variance: recall_runs are identical across
  repetitions because the indexes are deterministic. Variance needs
  independent index builds with different seeds, which is part of the
  same rerun.

## 6. Reproducibility (A-)

One command reruns the study, one regenerates RESULTS.md, versions and
seeds are recorded in results/env.json, the corpus is public and rebuilt
locally, and CI runs the test suite on Python 3.11 and 3.12.

Fixed in this change:

- tests/test_generate_results.py pins the six verdicts, the C2 check
  (4.75 agrees, 0.42 disagrees), the Wilson formula and the per-row sample
  sizes against the committed results/cells.json. The study's decision
  logic was previously untested.
- The site build fails if its JavaScript ports of the C2, Wilson, H6 and
  picker logic disagree with RESULTS.md (site/src/stats.check.mjs).

Remaining: no independent replication run. Needs one full rerun on a
second machine with the same pinned versions, then a diff of
results/cells.json.

## 7. Threats to validity (B+)

METHODS.md and AUDIT.md name the client asymmetry, Qdrant local mode, one
corpus and model, random versus correlated labels, version specificity,
possible pgvector contention, and the reduced Qdrant protocol (D10). The
direction of each bias is stated rather than corrected after the fact.

The one threat that reaches a verdict is Qdrant local mode (see H3 above).
The contention threat on pgvector latency needs a pgvector-only rerun on
an idle machine to resolve.

## 8. Related work (B)

RESEARCH.md cites primary sources for FAISS, HNSW, pgvector 0.8.0,
Qdrant, Filtered-DiskANN, the Big ANN NeurIPS'23 filtered track and
ANN-Benchmarks, and labels vendor evidence as vendor evidence. The novelty
claim is limited to a measurement contribution.

Gap: no record of the search itself (databases, query strings, date), so a
reader cannot judge coverage. Needs a literature search log; no compute.
This is a writing task outside the scope of this change, recorded here so
it is not lost.

## 9. Limitations (A-)

README, METHODS.md and AUDIT.md list the limits, and AUDIT.md grades the
build at 7,300 of 10,000 with every deduction itemized.

Fixed in this change: README and AUDIT.md quoted the C2 model's prediction
at 1 percent selectivity as "about 0.1". The generated C2 check and the
arithmetic (ef_search 40 times measured selectivity 0.0105) give 0.42. Both
files now say 0.42, matching RESULTS.md and the site's live calculator.

## Remaining gaps and what each needs

1. Qdrant server mode rerun: the Qdrant server binary on localhost, the
   58,999-chunk corpus rebuilt from SQuAD v1.1 with the model2vec
   embeddings, and the main, churn and hybrid cells at 300 queries x 3
   repetitions. Resolves H3, the Qdrant latency rows and the D10 sample
   asymmetry.
2. Per-query outputs: a runner change to save per-query recall, latency
   and per-question nDCG, then a full rerun. Enables bootstrap intervals,
   the paired H6 test and p99.
3. Breadth sweep with 5 runs per setting for matched-recall Pareto curves
   (ROADMAP item 2).
4. EXPLAIN plans for the two pgvector trap cells against the rebuilt
   database, to confirm or reject the planner mechanism.
5. A shared-BM25 pgvector hybrid arm, to restore H6's encoder control.
6. Churn depth (1, 10, 50 percent, several epochs) and FAISS IVF with
   remove_ids (ROADMAP item 3).
7. A second corpus or embedding model and a larger scale (ROADMAP items 4
   and 7), for external validity.
8. An independent replication run on a second machine.

Proposed for the study owner, not applied: relabel H3 to Inconclusive, and
decide whether H2 should include the post-churn cells.
