# Decisions

Each decision lists the options considered, the verdict, and the reason.
Newest last.

## D1: Corpus

Options: BEIR SciFact; BEIR NFCorpus; MS MARCO passages; SQuAD v1.1
paragraphs chunked to study scale.
Verdict: SQuAD v1.1, chunked.
Reason: SciFact (5,183 documents) and NFCorpus (about 3,600) are too
small for the 50k to 100k vector scale the study targets. MS MARCO's
terms restrict redistribution of derived data. SQuAD is CC BY-SA 4.0,
has real text, real questions with known source paragraphs (which gives
the hybrid cell its relevance labels for free), and chunks cleanly to
about 59k units. Its question set doubles as the hybrid query set, which
no other candidate offered.

## D2: Embedding model

Options: minishlab/potion-base-8M via model2vec; a sentence-transformers
model (for example all-MiniLM-L6-v2); OpenAI embeddings (paid, excluded
by the zero-spend rule).
Verdict: potion-base-8M via model2vec.
Reason: MIT licence, static embeddings that run fast on CPU, and it is
the established pattern in Jesun's P06 rag-eval-harness, so results are
comparable across the portfolio. 256 dimensions is also the size class
where the pack's memory calculation C1 is least favourable to raw
storage, which keeps the study honest about scale.

## D3: Qdrant deployment shape

Options: the production Qdrant server binary on localhost; qdrant-client
embedded local mode.
Verdict: embedded local mode, as the track brief specifies.
Reason: one Python harness, no extra service to install, and the brief
fixes this shape. The cost is recorded as a limitation: local mode is a
Python implementation, so its latency is not the server's latency and
its filtered recall is a floor, not the server's number. A server-mode
rerun is the first item of the Deep pass (REPORT.md, Next steps).

## D4: FAISS index

Options: IndexHNSWFlat; IndexIVFFlat; IndexFlat (exact).
Verdict: IndexHNSWFlat, with IDSelector filtering and two churn arms.
Reason: HNSW is the index class the other two backends also use, which
keeps the comparison about systems rather than algorithm families. Its
missing delete operation is exactly what the churn cell is designed to
expose. IVF, whose ids are removable, is named in the pack as the FAISS
churn baseline and is a Deep-pass addition.

## D5: Filter label design

Options: random labels only; natural labels only; both.
Verdict: both. A random skewed `tenant` label gives a clean selectivity
ladder at about 50, 10 and 1 percent. The `article` label gives a
correlated filter at about 1 percent, the case where the pack's C2
estimate warns its independence assumption breaks.
Reason: the regime map needs the contrast; either label alone would hide
one failure mode.

## D6: pgvector configurations

Options: defaults only; tuned only; both, in named arms.
Verdict: both. Main cells run iterative scan on with a tuned ef_search
(the documented, competent configuration). Trap cells run the shipped
defaults.
Reason: H1 is a claim about the gap between the two. Measuring only one
side would either hide the trap or hide the fix.

## D8: Qdrant local mode storage variant (amendment, recorded before any Qdrant result existed)

Options: embedded local mode on disk (SQLite store, as first written);
embedded local mode in memory.
Verdict: in memory.
Reason: the on-disk variant ingested about 1,000 points per minute on
this VM (measured directly in its store: 26,622 of 58,999 points after
about 27 minutes), which put the full study out of reach. The local
engine, its search semantics and its limitations are the same in both
variants; only the storage medium changes. The amendment was made and
committed before a single Qdrant number was measured, so it cannot be
result-driven. The matching amendment note, first written into SPEC.md,
now lives in D12, which restores SPEC.md to its locked text. The client
also warns that payload indexes have no effect in local mode; the setup
calls are kept for parity with the server configuration, and the warning
is recorded in AUDIT.md.

## D7: Hybrid fusion location

Options: one shared fusion implementation for all backends; each
backend's native path.
Verdict: native where one exists (Qdrant Query API RRF; pgvector SQL
RRF), application-level shared RRF for FAISS, which has no native
hybrid. The sparse encoder and the RRF constant (k = 60) are shared, so
the comparison stays about systems. The pgvector lexical arm uses
PostgreSQL full-text search, its native path, and that exception is
named in METHODS.md.

## D9: Per-phase result checkpoints

The first full Qdrant run was lost when the VM rebooted about 60
minutes into the measurement: the runner wrote results only when a
whole backend finished, so no Qdrant number survived. No number from
that attempt is used anywhere. The runner now flushes the results
file after every phase (after the main cells, after the hybrid cell,
after each churn cell) through a checkpoint callback. The measurement
protocol is unchanged: same cells, same order, same repetitions. Only
the write timing changed. The Qdrant backend was then re-run in full
under the same protocol.

## D10: Qdrant query count and repetitions reduced, with disclosure

The full-protocol Qdrant re-run (300 queries, 3 repetitions) passed 60
minutes without finishing its main cells phase on this VM: local mode
answers each query with a Python exact scan over 58,999 points, at
roughly 0.7 seconds per query and rising with filter complexity. The
client itself warns that local mode is not recommended above 20,000
points. Waiting for the full cell set was projected at about 90
minutes for this backend alone, after two earlier attempts had already
been lost (slow on-disk ingestion, then the VM reboot of D9).

Verdict: the Qdrant backend runs with 100 queries and 2 repetitions;
FAISS and pgvector keep the full 300 and 3. The deviation is recorded
here before the reduced run starts, and it is also visible in
results_qdrant/env.json (n_queries 100, reps 2) next to the main
results/env.json (300, 3). Effects, stated plainly: Qdrant recall is
exact by construction in local mode, so the smaller sample does not
change any recall conclusion; Qdrant latency percentiles rest on 100
queries per cell instead of 300, so their tails are less stable; the
hybrid cell is unchanged (it uses its own fixed set of 250 questions
for every backend). No Qdrant number from the abandoned full-protocol
attempts is used anywhere.

## D11: H2 cell set disclosed, post-churn cells left out (recorded after the results)

HYPOTHESES.md H2 lists the post-churn cell among the cells compared, but
generate_results.py has always computed H2 over the five main filter
cells only. The post-churn records run different arms per backend
(FAISS raw and bookkeeping, pgvector iterative, Qdrant native), so they
are not a like-for-like main cell. Verdict: keep the computation on the
five main cells, and say so in the H2 evidence line, which now names the
cell set and points here. This is a deviation from the pre-registered
wording, disclosed rather than silently carried. Whether H2 should be
recomputed with the post-churn cells included is an open question for
the study owner; no rerun is needed either way, since the churn records
exist in results/cells.json.

## D12: SPEC.md restored to its locked text; amendment note moved here (recorded 2026-11-08)

SPEC.md and HYPOTHESES.md were committed together in 838e6da, before any
code or result, and that commit is tagged proposal-v1. Commit 7ed6d8d
later edited SPEC.md in place to record the D8 amendment, after the FAISS
results of 4b559bd already existed. A locked plan is never edited after
its lock, so SPEC.md is restored byte for byte to its 838e6da text and a
test (tests/test_layout.py) pins its SHA-256. The amendment is not lost:
D8 above is the decision, and the note that sat in SPEC.md is kept here
verbatim. The bullet it amended read "Qdrant (qdrant-client, embedded
local mode on disk)"; the edit dropped "on disk" and added:

> Amendment, recorded after pre-registration and before any Qdrant
> result existed: the in-memory storage variant of local mode is used,
> because the on-disk variant ingested about 1,000 points per minute on
> the study VM (DECISIONS.md, D8). The local engine and its semantics
> are identical in both variants.

Effect: none on any number or verdict; the study ran the in-memory
variant, as D8 records.
## D13: Post-registration amendment: paired per-question bootstrap for the hybrid gains (registered before the run)
Numbering note (added 2026-11-17, when this entry was merged to main): this amendment was written as D11 in the local record of 2026-11-16 and is cited as D11 in version 2 of the preprint (Zenodo DOI 10.5281/zenodo.24283784). On main, D11 and D12 were already taken by later records, so the amendment is filed here as D13. Same amendment, same dates, no content change; its output files keep their recorded names (results/amendment_d11.json, src/vectorbench/amendment_d11.py).

Recorded 2026-11-16, before any computation under this amendment ran.
Motivation: the paper reports the H6 hybrid gains as mean nDCG@10
differences (FAISS plus 0.047, pgvector plus 0.017, Qdrant plus 0.069)
with no paired test, and says so in its limitations. This amendment
adds paired bootstrap intervals for the gain, per backend, from a
rerun of the hybrid arms that records per-question nDCG@10 for the
dense, sparse, and hybrid arms.

Specification, frozen before the run:

- Same corpus, embeddings, question sample (250 SQuAD questions, seed
  99), relevance rule, and RRF rule (k = 60) as the registered hybrid
  cell. The rerun's aggregate nDCG@10 per arm must reproduce the
  committed results within rounding (0.001); if an arm does not
  reproduce, the amendment reports the discrepancy instead of the
  interval for that backend.
- 2,000 bootstrap resamples over the 250 questions, with replacement,
  seed 20261116. In each resample, the mean hybrid-minus-dense
  nDCG@10 difference is recomputed from the paired per-question
  scores. Reported per backend: the point gain, the bootstrap mean,
  and the 2.5 and 97.5 percentile interval.
- Scope limit, stated in advance: the pgvector hybrid arm runs
  inside PostgreSQL, which is not available in the reproduction
  environment (no PostgreSQL, no container runtime), so its
  per-question scores cannot be regenerated there. The amendment
  covers the FAISS and Qdrant arms; the pgvector gain keeps its
  aggregate-only status, and the paper will say exactly that.
- No verdict changes: H6 stays Partially supported as registered.
  The intervals are reported as an amendment in version 2 of the
  preprint (Zenodo DOI 10.5281/zenodo.24282173).

Output: results/amendment_d11.json, written by the amendment script;
this entry gains no retroactive edits.

D13 results note (appended after the runs, 2026-11-16): both
covered arms reproduced their committed aggregates exactly (FAISS
dense 0.374, hybrid 0.421; Qdrant dense 0.387, hybrid 0.456), so
the intervals stand as registered. FAISS: point gain plus 0.0468,
95 percent interval plus 0.0296 to plus 0.0645. Qdrant: point gain
plus 0.0694, interval plus 0.0519 to plus 0.0869. Both intervals
exclude zero and the registered 0.02 line. The pgvector arm was
not covered (no PostgreSQL in the reproduction environment); its
plus 0.017 gain keeps its aggregate-only status. H6 stands
Partially supported as registered. Record:
results/amendment_d11.json; script src/vectorbench/amendment_d11.py.

## D17: Post-registration amendment: pgvector per-query recall intervals on a Docker host (registered 2026-11-18, before the run)

D14 could not compute pgvector per-query intervals: per-query values
were never saved and no PostgreSQL was available on the machines of
record, so only the four cells at exactly 1.000 got (degenerate)
intervals and the other five carry a labelled slot-level Wilson
supplement. This amendment registers the run D14 pointed at.

Specification, frozen before the run: the pgvector cells are
re-executed against the official pgvector/pgvector:pg16 container
(PostgreSQL 16, pgvector 0.8.0) on the Dell PowerEdge R610, with
run_pgvector mirrored through the repo own run_cell (same build, same
breadth tuning, same trap and churn sequence). Per-query recall is
captured from repetition 1 for all nine recall cells (five main
iterative cells, two trap cells, two post-churn cells). Intervals use
the D14 method unchanged (per-query bootstrap, 10,000 resamples, seed
20261117, percentile 2.5 and 97.5), imported from amendment_d14.
Validation rule (D14): a cell interval is reported only if the fresh
aggregate reproduces the committed results_pg/cells.json recall@10
within 0.001; otherwise the discrepancy is reported instead of an
interval. The hybrid cell is out of scope (it is not one of the nine
recall cells).

Machine history: staged on BlackBoxV2 (route lost before it ran),
re-registered on BlackBoxV3 (no container runtime there), executed on
the R610 under the order of 2026-11-18. Same plan, no content change.

Output: results/amendment_d17.json, written by
src/vectorbench/amendment_d17.py, with the per-query arrays saved.
No verdict changes: H1 to H6 stand as registered.

D17 setup note (2026-11-18): amendment_d14.py is not on the repository
main (it lives on the unmerged gap-closure records branch), so the
file was copied into this clone unchanged from the gap-closure working
clone, md5-verified, purely as the method source this amendment
imports. No content change to the method.

D17 outcome (2026-11-18): executed on the R610 as registered, against
the official pgvector/pgvector:pg16 image as pulled today, which now
ships PostgreSQL 16.16 with pgvector 0.8.7 (the committed record ran
on PostgreSQL 16.15 with pgvector 0.8.0). Five of the nine cells
reproduce within the 0.001 validation line and carry per-query
bootstrap intervals (10,000 resamples, seed 20261117): unfiltered
0.9787 [0.971, 0.985]; tenant_t0 1.000 [1.000, 1.000]; tenant_t5 1.000
[1.000, 1.000]; trap tenant_t5 1.000 [1.000, 1.000]; post-churn
tenant_t5 1.000 [1.000, 1.000]. Four cells do NOT reproduce and carry
no interval, per the registered rule: tenant_t2 fresh 1.000 vs
committed 0.979; article_group fresh 1.000 vs committed 0.988;
trap tenant_t2 fresh 1.000 vs committed 0.486; post-churn unfiltered
fresh 0.979 vs committed 0.976 (outside by 0.003). On this pgvector
version the filtered cells return the exact filtered top-10 (recall
1.0), including the trap configuration whose overfiltering the study
measures; the committed behaviour does not appear. The per-query
arrays for all nine cells are saved in results/amendment_d17.json
either way. No verdict changed.

D17 addendum (2026-11-18, registered before the run it covers): a
second execution of the same module, unchanged, against the archived
official image pgvector/pgvector:0.8.0-pg16 (pgvector 0.8.0, the
version of record), to test whether the four non-reproducing cells
reproduce under the environment of record. Same validation rule.
Output: results/amendment_d17_pg080.json.

D17 addendum 2 (2026-11-18, registered before the run it covers):
diagnosis and one-step environment repair. On both container
executions the filtered cells returned the exact filtered top-10
(recall 1.0), including the trap cell. EXPLAIN on the trap query
showed the planner choosing a bitmap heap scan on the tenant B-tree
plus a sort (an exact plan), with a row estimate of 297 against 6,342
actual tenant_t2 rows: the freshly built container table carries no
statistics (pg_stat shows no analyze, ever), so the exact plan looks
cheap and the HNSW index is never used. The committed database, a
long-lived install, carried analyzed tables. After a manual ANALYZE
on the run table the same EXPLAIN flips to an index scan on
chunks_hnsw with the filter applied after the scan, the mechanism
the study measures. The repair is one step: amendment_d17.py runs
ANALYZE on the chunks table immediately after the adapter build,
restoring the environment of record; the module is otherwise
unchanged, the run is against the 0.8.0 container, and the output is
results/amendment_d17_pg080_analyzed.json. Same validation rule.

D17 final outcome (2026-11-18): three registered executions on the
R610. Executions 1 (pgvector 0.8.7, current pg16 image) and 2
(pgvector 0.8.0, archived image) ran without table statistics and
are recorded in results/amendment_d17.json and
results/amendment_d17_pg080.json; execution 3 (0.8.0 plus the
addendum 2 ANALYZE step) is recorded in
results/amendment_d17_pg080_analyzed.json. The first outcome entry
above framed the gap as a version difference; the addendum 2
diagnosis supersedes that framing: the operative difference was
planner statistics, not the pgvector version. Under the validation
rule, eight of the nine cells carry a per-query bootstrap interval
from at least one execution (10,000 resamples, seed 20261117):
unfiltered 0.978 [0.971, 0.985]; tenant_t0 1.000 [1.000, 1.000];
tenant_t2 0.979 [0.973, 0.985]; tenant_t5 1.000 [1.000, 1.000]; trap
tenant_t2 0.486 [0.464, 0.508] (the analyzed execution reproduced
the committed 0.4857 exactly); trap tenant_t5 1.000 [1.000, 1.000];
post-churn unfiltered 0.976 [0.969, 0.983] (the 0.8.0 execution
reproduced the committed value exactly); post-churn tenant_t5 1.000
[1.000, 1.000]. One cell carries no interval: article_group returned
1.000 in all three environments against the committed 0.988, so no
execution validated for it; its per-query arrays are saved in all
three output files. Beside the FAISS intervals from D14 (unfiltered
0.967 [0.957, 0.976]; tenant_t2 0.868 [0.850, 0.885]; tenant_t5
tight 0.413 [0.393, 0.433]; article_group 0.356 [0.325, 0.388]), the
pgvector side of the study now has per-query uncertainty for eight
of nine cells. No verdict changed.
