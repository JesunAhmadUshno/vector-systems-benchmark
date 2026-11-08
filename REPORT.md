# Report

The study report under the portfolio standard v2. The locked plan is
SPEC.md plus HYPOTHESES.md (commit 838e6da, tag proposal-v1); the
generated numbers are in RESULTS.md; deviations are in DECISIONS.md.
Every number below is copied from RESULTS.md or results/readme_table.md,
both regenerated from results/*.json by
`python -m vectorbench.generate_results` (CI fails if they drift).

## Status and verdict

Verdict: Functional. The harness ran end to end on all three engines and
its outputs are committed (results/cells.json, results_pg/,
results_qdrant/); the tests pass in CI on Python 3.11 and 3.12; RESULTS.md
regenerates unchanged from the evidence in CI. The plan was locked before
any code (838e6da precedes the harness in 4b559bd).

Why not Evaluated (METHOD section 4, performance profile), item by item:

- Warm-up and every run: there are no warm-up runs, and only the median
  repetition's p50 and p95 latency were kept; per-run latencies were not
  saved, so not every run is reported.
- Co-tenancy: load on the machine was not recorded at each run. The
  pgvector run shared the VM with a lost Qdrant attempt (AUDIT.md, Run
  integrity), disclosed but not measured.
- Baselines under the same resources: Qdrant ran in embedded local mode,
  not the server product, and under a reduced protocol (100 queries x 2
  repetitions against 300 x 3; DECISIONS.md D10). The FAISS IVF churn
  baseline was not run.
- Machine of record: results/env.json names the CPU (AMD EPYC 9D25) and
  the run date; the host is described only as "the study VM".
- Review: no second reader has yet re-derived the headline numbers from
  results/*.json (lifecycle stage 7).

## Background

Production retrieval rarely runs unfiltered. A RAG system answers inside a
tenant, a permission boundary, a language, a date range. Under those
filters, a vector engine can fail silently: it returns fewer results than
asked, or worse ones, and raises no error. The pgvector documentation
names the failure "overfiltering". For a user of a permission-scoped
assistant, a silent retrieval miss becomes a confident wrong answer. A
deleted document that still appears in results is the same class of harm.

Measure, on one shared corpus of real text and one node, how FAISS,
PostgreSQL with pgvector, and Qdrant behave as three workload variables
change: metadata filter selectivity, update churn, and hybrid (lexical
plus dense) demand. The output is a measured regime map, not a ranking.
Hypotheses were pre-registered before any experiment code was written
(see SPEC.md and HYPOTHESES.md; the git history shows the order).

The literature base is in RESEARCH.md; the design is in SPEC.md and the
formulas, controls and threats in METHODS.md.

## Results

No universal winner, and the map has sharp edges. Unfiltered, FAISS is
the fastest by a wide margin (p95 0.47 ms at recall 0.967, against
3.05 ms for pgvector and 299.53 ms for embedded Qdrant). Under a tight
filter at about 1 percent selectivity, FAISS recall falls to 0.413 with
a shortfall rate of 0.267: post-filtering an HNSW candidate set starves
as selectivity drops. pgvector with iterative scan holds recall 1.000
in the same cell. Its documented overfiltering trap turns out to live
one selectivity band higher than the literature suggests: at shipped
defaults and about 12 percent selectivity it returns a mean of 4.86
results per query with a shortfall rate of 0.990, while at 1 percent
no trap appears: the measured mean returned there is 10.00 where the
candidate-starvation model predicts about 0.42 (ef_search 40 times selectivity 0.0105), the pattern the
research pack's row 10 attributes to the planner leaving the ANN index
at very low selectivity (H1 is refuted as pre-registered, and the
trap's measured location is the finding). Qdrant in embedded local
mode is exact by construction, recall 1.000 in every cell, and its
latency (up to 3.69 s p95 in the tight cell) measures a Python
brute-force scan, not the server product; the server's filtered HNSW
stays unmeasured here (next step 1). Under a 10 percent churn cycle,
FAISS without external bookkeeping keeps serving deleted vectors at a
stale rate of 0.113; with bookkeeping, and in pgvector and Qdrant, the
stale rate is 0.000. Hybrid fusion pays where the lexical arm is the
shared BM25 encoder (FAISS +0.047 nDCG@10; Qdrant native RRF +0.069)
and barely where it is PostgreSQL full-text search (+0.017).

Headline table (results/readme_table.md, generated):

| Backend | Unfiltered recall@10 | Unfiltered p95 ms | Tight filter recall@10 | Tight shortfall | Post-churn recall drop | Hybrid nDCG@10 (dense to hybrid) |
|---|---|---|---|---|---|---|
| faiss | 0.967 | 0.47 | 0.413 | 0.267 | 0.009 | 0.374 to 0.421 |
| pgvector | 0.978 | 3.05 | 1.000 | 0.000 | 0.002 | 0.375 to 0.392 |
| qdrant | 1.000 | 299.53 | 1.000 | 0.000 | 0.000 | 0.387 to 0.456 |

Full generated results, including the trap cell, the churn cells, the
tuning ladders, the Wilson intervals and the per-hypothesis evidence:
RESULTS.md.

## Hypotheses scored, misses shown

| Hypothesis | Pre-registered prediction (HYPOTHESES.md) | Verdict (RESULTS.md, generated) | Reading after review |
|---|---|---|---|
| H1 | pgvector trap at defaults in the tight cell; iterative scan closes it | Refuted (miss) | No trap at 1 percent at defaults (mean returned 10.00 against a C2 prediction of 0.42); the trap appears one band up, at about 12 percent (shortfall 0.990). The planner mechanism is attributed to the research pack, not verified here (no EXPLAIN plan captured). |
| H2 | No universal winner across the cells | Supported | Computed over the five main filter cells only; the post-churn cell listed in the hypothesis is left out (DECISIONS.md D11, a disclosed deviation). |
| H3 | Qdrant tight-cell recall at or above 0.90, shortfall 0 | Supported | Does not test the hypothesis for the product: embedded local mode is exact brute force, so it cannot fail. Relabel to Inconclusive is proposed for the Owner and not applied. |
| H4 | FAISS lowest unfiltered p95 at recall at or above 0.95 | Supported | Compares deployed shapes (in-process library against client and socket), not index algorithms. |
| H5 | Churn freshness per backend, recall drop below 0.05 | Supported | All five lines pass; one churn rate and one cycle only. |
| H6 | Hybrid beats dense by at least 0.02 nDCG@10 for every backend | Partially supported (partial miss) | FAISS +0.047 and Qdrant +0.069 pass; pgvector +0.017 misses the bar, and its lexical arm is PostgreSQL full-text search, not the shared BM25. No paired test. |

Standing checks: the C2 check agrees at about 12 percent selectivity
(predicted 4.75, measured 4.86) and disagrees at about 1 percent
(predicted 0.42, measured 10.00). The exactness check is a harness test
(tests/test_faiss_adapter.py and the adapter tests), not a result.

## Evidence trace for the headline

| Number | Source |
|---|---|
| FAISS tight-cell recall@10 0.413, shortfall 0.267 (Wilson 95% 0.220 to 0.319, 300 queries) | RESULTS.md, "about 1 percent selectivity (tight)"; results/cells.json, backend faiss, cell tenant_t5 |
| pgvector iterative tight-cell recall@10 1.000, shortfall 0.000 | same table, pgvector iterative |
| pgvector defaults at about 12 percent: shortfall 0.990 (Wilson 95% 0.971 to 0.997), mean returned 4.86 | RESULTS.md, "Trap cell, about 10 percent selectivity, defaults"; results/cells.json, trap, tenant_t2 |
| pgvector defaults at about 1 percent: mean returned 10.00 against C2 prediction 0.42 | RESULTS.md, C2 check sentence |

No headline number lacks an evidence file in the repository.

## Limitations

- Single node, CPU only, corpus fits in RAM. Nothing here speaks about
  clusters, GPUs, or billion-scale data.
- Qdrant runs in embedded local mode, a Python implementation, not the
  production server. Its latency is not the server's latency, and its
  filtered recall is exact by construction, so it cannot evidence the
  server product's filtered recall at all. A server-mode rerun is
  next step 1.
- Qdrant ran at 100 queries and 2 repetitions against 300 and 3 for
  the other backends (DECISIONS.md D10): local mode costs about a
  second per query at this scale. Its latency percentiles rest on the
  smaller sample.
- FAISS runs in process while the others run through clients, so latency
  compares deployed shapes, not only index algorithms.
- One corpus, one embedding model, one chunk size, one churn rate (10
  percent). Regime boundaries can move with any of them.
- Hybrid relevance is derived from SQuAD's paragraph structure, not from
  human relevance judgments.

Itemized limitations of this build, from the audit (AUDIT.md links here):

- Qdrant server product not measured: local mode is exact by construction, so the Qdrant recall column cannot evidence the deployed product's filtered search.
- Qdrant protocol asymmetry (D10): 100 queries and 2 repetitions against 300 and 3 for the other backends; latency tails less stable.
- Single corpus, single embedding model, single chunk size, one scale (58,999 chunks): regime boundaries may move with any of them.
- Latency compares three client shapes (in-process, SQL over a socket, embedded Python), so it ranks deployed shapes, not index algorithms.
- Hybrid limits: no paired significance test, and the pgvector lexical arm is PostgreSQL full-text search rather than the shared BM25, so its hybrid gain is not encoder-controlled.
- Breadth tuned once on the unfiltered cell and frozen by design, so there is no matched-recall Pareto frontier; latency is compared at unmatched recall points.
- pgvector latency may carry contention from a parallel run (see Run integrity); disclosed, not corrected.
- One churn rate (10 percent) and one churn pattern.
- Jev claim_check returned REVIEW (noul 0.47), not clear; the headline claim ships on a documented self-audit with one softened clause.
- No replication pass: one run per backend, repetitions within the run only.
- Memory and build cost per backend not measured (the research pack's C1 estimate stays unchecked until the Deep pass).

## Review findings (2026-11-07)

A review against a research rubric, done on the committed evidence
(results/*.json, RESULTS.md, SPEC.md, HYPOTHESES.md, METHODS.md, AUDIT.md,
DECISIONS.md and the git history). It was first published as
docs/research-review.md; its content is kept here, without the rubric
marks, which are internal. The rule applied then: every gap that can
be closed without a GPU, a paid API or a long benchmark rerun is closed.

Summary, one line per criterion:

- Research question: Specific, falsifiable, stated before code, tied to a real failure (silent shortfall).
- Hypotheses: Six pre-registered, with thresholds and falsifiers; one undisclosed cell-set deviation, now disclosed (D11).
- Method and controls: Same corpus, embeddings, queries and ground truth everywhere; frozen breadth; one deployment-shape confound.
- Baselines: Exact NumPy ground truth and a defaults arm for pgvector; Qdrant server and FAISS IVF baselines missing.
- Statistics and uncertainty: Fixed thresholds, no inference; proportion intervals added here; recall, nDCG and latency still have none.
- Reproducibility: One-command harness, pinned versions, seeds, generated results, a test for the decision logic (added here).
- Threats to validity: Named in METHODS.md and AUDIT.md; the H3 local-mode threat undercuts a published verdict.
- Related work: Primary sources for each engine and for filtered ANN; vendor claims labelled; no systematic search record.
- Limitations: Itemized limitations; the C2 headline number was inconsistent and is fixed here.

Overall: a strong measurement study whose recall and shortfall findings
are well supported, whose latency comparison is a deployed-shape
comparison, and whose Qdrant results speak only for the embedded engine.

### R1. Research question

SPEC.md asks how FAISS, pgvector and Qdrant compare on recall, latency,
filtered recall, freshness and hybrid quality as filter selectivity, churn
and hybrid demand change, and frames the output as a regime map rather
than a ranking. The question is narrow enough to answer on one node and
the harm it targets (a filtered query that silently returns too few
results) is concrete. The git order (838e6da before 4b559bd) shows the
question and hypotheses were fixed before any experiment code.

No gap.

### R2. Hypotheses

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

### R3. Method and controls

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

### R4. Baselines

Exact brute-force NumPy top 10 is the reference for every recall number,
and the harness tests require each adapter to reach recall 1.000 in exact
mode before its approximate numbers count. pgvector has a defaults arm
and an iterative-scan arm, which is the right within-system baseline for
H1.

Gaps (all need reruns, none fixable from committed data):

- Qdrant server mode, the production product (next step 1).
- FAISS IVF with remove_ids as the churn baseline the research pack names
  (next step 3).
- A filtered-ANN method designed for the problem, such as
  Filtered-DiskANN, cited in README but not run.

### R5. Statistics and uncertainty

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
  (40 to 320) per backend and cell with 5 runs each (next step 2).
- Repetitions add no recall variance: recall_runs are identical across
  repetitions because the indexes are deterministic. Variance needs
  independent index builds with different seeds, which is part of the
  same rerun.

### R6. Reproducibility

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

### R7. Threats to validity

METHODS.md and AUDIT.md name the client asymmetry, Qdrant local mode, one
corpus and model, random versus correlated labels, version specificity,
possible pgvector contention, and the reduced Qdrant protocol (D10). The
direction of each bias is stated rather than corrected after the fact.

The one threat that reaches a verdict is Qdrant local mode (see H3 above).
The contention threat on pgvector latency needs a pgvector-only rerun on
an idle machine to resolve.

### R8. Related work

RESEARCH.md cites primary sources for FAISS, HNSW, pgvector 0.8.0,
Qdrant, Filtered-DiskANN, the Big ANN NeurIPS'23 filtered track and
ANN-Benchmarks, and labels vendor evidence as vendor evidence. The novelty
claim is limited to a measurement contribution.

Gap: no record of the search itself (databases, query strings, date), so a
reader cannot judge coverage. Needs a literature search log; no compute.
This is a writing task outside the scope of this change, recorded here so
it is not lost.

### R9. Limitations

README, METHODS.md and AUDIT.md list the limits, and AUDIT.md itemized
them (now in Limitations above).

Fixed in this change: README and AUDIT.md quoted the C2 model's prediction
at 1 percent selectivity as "about 0.1". The generated C2 check and the
arithmetic (ef_search 40 times measured selectivity 0.0105) give 0.42. Both
files now say 0.42, matching RESULTS.md and the site's live calculator.

### Remaining gaps and what each needs

1. Qdrant server mode rerun: the Qdrant server binary on localhost, the
   58,999-chunk corpus rebuilt from SQuAD v1.1 with the model2vec
   embeddings, and the main, churn and hybrid cells at 300 queries x 3
   repetitions. Resolves H3, the Qdrant latency rows and the D10 sample
   asymmetry.
2. Per-query outputs: a runner change to save per-query recall, latency
   and per-question nDCG, then a full rerun. Enables bootstrap intervals,
   the paired H6 test and p99.
3. Breadth sweep with 5 runs per setting for matched-recall Pareto curves
   (next step 2).
4. EXPLAIN plans for the two pgvector trap cells against the rebuilt
   database, to confirm or reject the planner mechanism.
5. A shared-BM25 pgvector hybrid arm, to restore H6's encoder control.
6. Churn depth (1, 10, 50 percent, several epochs) and FAISS IVF with
   remove_ids (next step 3).
7. A second corpus or embedding model and a larger scale (next steps 4
   and 7), for external validity.
8. An independent replication run on a second machine.

Proposed for the study owner, not applied: relabel H3 to Inconclusive, and
decide whether H2 should include the post-churn cells.

## Next steps (the Deep pass, in evidence order)

Formerly ROADMAP.md. The Build pass measures the regime map at one
operating point per backend, one churn cycle, and one hybrid
configuration. Items are ordered by how much each one strengthens or
threatens the published verdicts. References elsewhere to "next step N"
point to this list.

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

## Citations

- Douze et al., "The Faiss library", arXiv:2401.08281.
- Malkov and Yashunin, "Efficient and robust approximate nearest
  neighbor search using Hierarchical Navigable Small World graphs",
  IEEE TPAMI 42(4), 2020.
- pgvector documentation and 0.8.0 release notes, github.com/pgvector/pgvector.
- Qdrant documentation: indexing, hybrid queries, optimizer,
  docs.qdrant.tech.
- Gollapudi et al., "Filtered-DiskANN", WWW 2023.
- Simhadri et al., "Results of the Big ANN NeurIPS'23 competition",
  NeurIPS 2025 Datasets and Benchmarks.
- Aumuller, Bernhardsson, Faithfull, "ANN-Benchmarks", Information
  Systems, 2020.
- Rajpurkar et al., "SQuAD: 100,000+ Questions for Machine Comprehension
  of Text", EMNLP 2016 (dataset licence CC BY-SA 4.0).

Licence: Apache-2.0 for code. The corpus is not redistributed here; it is
built locally from the public SQuAD release.

Licence: Apache-2.0 for code. The corpus is not redistributed here; it is
built locally from the public SQuAD release.
