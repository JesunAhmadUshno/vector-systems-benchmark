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

## D14: Post-registration amendment: per-cell recall@10 uncertainty intervals (registered before the run)

Recorded 2026-11-17, before any computation under this amendment ran.
Motivation: RESULTS.md states that recall carries no interval because
per-query values were not saved ("Recall, nDCG and latency carry no
interval: per-query values were not saved"). This amendment adds
per-query bootstrap intervals for the headline recall cells of all
three systems, including the post-churn cells, without changing any
verdict.

Specification, frozen before the run:

- Method: per-query bootstrap, 10,000 resamples over the queries of
  each cell, with replacement, seed 20261117; the reported interval
  is the 2.5 and 97.5 percentile of the resample means of per-query
  recall@10.
- Source of per-query values, per system, stated in advance:
  - FAISS: per-query recall is re-derived by re-running the FAISS
    cells (the five main cells, plus the post-churn raw and
    bookkeeping arms on the unfiltered and tight cells) with the
    repo harness at the committed frozen breadth (40) on the cached
    corpus artifacts in data/ (the same artifacts the D13 amendment
    used). Validation rule: each re-derived cell aggregate must
    reproduce the committed results/cells.json recall@10 within
    0.001, or the interval for that cell is not reported and the
    discrepancy is reported instead. Recall is deterministic across
    repetitions in the committed record (recall_runs are identical),
    so one repetition is run for the per-query capture.
  - Qdrant (embedded): every committed Qdrant cell, main and
    post-churn, records recall@10 of exactly 1.000. Per-query
    recall@10 cannot exceed 1.0, so a mean of exactly 1.000 forces
    every per-query value to 1.0; the bootstrap interval is the
    degenerate interval [1.000, 1.000]. No rerun is needed or run
    for this.
  - pgvector: per-query values were not saved and PostgreSQL is
    not available in this environment, so per-query values cannot
    be re-derived here. Cells at exactly 1.000 get the same
    degenerate interval as Qdrant. For the remaining pgvector cells
    no per-query interval is claimed; the output instead records
    them as not computable from the committed records, with a
    supplementary slot-level Wilson interval on the total hit
    count (hits = recall@10 x n_queries x 10, over n_queries x 10
    returned slots), explicitly labelled as treating slots within
    a query as independent and therefore narrower than a per-query
    interval would be.
- Post-churn stale rate: RESULTS.md already carries a Wilson
  interval over returned slots for every churn cell. Where per-query
  returned lists are re-derived (FAISS), a per-query stale-share
  bootstrap (same seed and resample count) is reported alongside.
- No verdict changes: H1 to H6 stand as registered. The intervals
  are an amendment record only.

Output: results/amendment_d14.json, written by the amendment script
src/vectorbench/amendment_d14.py; the re-derived FAISS per-query
recall arrays are saved in the same file.

D14 results note (appended after the run, 2026-11-17): every
re-derived FAISS aggregate reproduced its committed recall@10
within 0.000003, so all FAISS intervals stand as registered. FAISS
per-query bootstrap intervals (300 queries): unfiltered 0.967
[0.957, 0.976]; tenant_t0 0.952 [0.941, 0.962]; tenant_t2 0.868
[0.850, 0.885]; tenant_t5 (tight) 0.413 [0.393, 0.433];
article_group 0.356 [0.325, 0.388]; post-churn raw unfiltered
0.866 [0.853, 0.878] with per-query stale share 0.113 [0.102,
0.125]; post-churn raw tight 0.391 [0.371, 0.412] with stale share
0.105 [0.093, 0.117]; post-churn bookkeeping unfiltered 0.958
[0.947, 0.968], tight 0.391 [0.371, 0.412], stale 0.000
[0.000, 0.000]. Qdrant embedded: all seven cells degenerate at
[1.000, 1.000]. pgvector: the four cells at exactly 1.000 are
degenerate; the five remaining cells (unfiltered 0.978, tenant_t2
0.979, article_group 0.988, post-churn unfiltered 0.976, trap
tenant_t2 0.486) carry no per-query interval, as registered, with
slot-level Wilson intervals on total hits recorded in the output
file as a labelled supplement only. No verdict changed.

## D15: Post-registration amendment: Qdrant server-mode rerun at the matched protocol (registered before the run)

Recorded 2026-11-17, before the server binary was downloaded or any
computation under this amendment ran. This is Deep step 1 of
REPORT.md ("Next steps"), the study's largest named limitation:
the committed Qdrant numbers were produced by the embedded local
mode, whose filtered search is exact brute force by construction,
at a reduced protocol (100 queries x 2 repetitions, D10), so they
cannot evidence the production server's filtered HNSW.

Specification, frozen before the run:

- Server: the official Qdrant binary release, downloaded into a
  scratch directory outside the repo; the exact version, source
  URL and file hash are recorded in the output file. The server
  runs on localhost with its storage in the scratch directory.
  Nothing is installed system-wide.
- Client and configuration: the repo's Qdrant adapter logic
  (qdrant-client, collection with dense cosine vectors, HNSW
  m = 32, ef_construct = 200, sparse BM25 vector, payload indexes
  on tenant and article created before ingestion), with only the
  client connection changed to the server URL.
- Protocol: the matched protocol of the other two systems, 300
  queries x 3 repetitions, on the cached corpus artifacts in
  data/. Breadth is tuned on the unfiltered cell with the repo's
  ladder rule (first of 40, 80, 120, 200, 320 reaching recall@10
  at or above 0.95) and frozen, exactly as the registered study
  ran it.
- Cells: the five main cells (unfiltered, tenant_t0, tenant_t2,
  tenant_t5 tight, article_group), then the registered churn step
  (delete 10 percent, insert an equal number of held-out chunks,
  seeds as in the harness) and the two post-churn cells
  (unfiltered, tight), with stale rate. The hybrid cell is out of
  scope for this amendment; the registered comparison is recall.
- Per-query recall@10 is saved for every cell (the D14 lesson), and
  per-query bootstrap intervals (same method as D14) are reported
  for the server cells.
- Comparison, stated in advance: server recall@10 per cell is
  compared against the committed embedded-mode numbers, and the
  report states plainly whether three headline readings change:
  the 1.000 unfiltered recall, the hold at about 1 percent
  selectivity (tight cell recall 1.000, shortfall 0), and the zero
  stale rate after churn.
- No verdict changes in this amendment: H3's published verdict
  stands as registered; this amendment supplies the server
  evidence H3's caveat says is missing, and any relabelling is a
  decision for the study owner.

Output: results/amendment_d15.json, written by the amendment script
src/vectorbench/amendment_d15.py.

D15 results note (appended after the run, 2026-11-17): server
v1.20.2 (official release, musl build; the gnu build of the same
release needs GLIBC 2.43 and does not start on this VM's GLIBC
2.39, recorded in the output file). Tuning chose breadth 40, the
same frozen value as the embedded record (ladder recall 0.9923).
Server recall@10 at 300 queries x 3 repetitions, against the
committed embedded numbers: unfiltered 0.990 [bootstrap 0.985,
0.993] against embedded 1.000; tenant_t0 1.000 against 1.000
(repetitions varied on the server: 1.000, 0.971, 0.931, unlike
the deterministic embedded record; the headline value follows the
harness convention of repetition 1); tenant_t2 1.000 against
1.000; tenant_t5 tight 1.000, shortfall 0.000, against 1.000;
article_group 1.000 against 1.000; post-churn unfiltered 0.960
[0.951, 0.969] against 1.000, a drop of 0.029 from the server's
own pre-churn cell, inside the H5 line of 0.05; post-churn tight
1.000 against 1.000. Stale rate 0.000 in both post-churn cells,
as committed. The three headline readings, plainly: the 1.000
unfiltered recall does NOT hold exactly on the server (0.990;
the embedded 1.000 was an artifact of exact search); the hold at
about 1 percent selectivity DOES hold on the server product
(tight recall 1.000, shortfall 0, so H3's falsification rule is
not triggered); the zero stale rate after churn DOES hold.
Server latency is far below the embedded record (tight-cell p95
34.01 ms against 3,690.63 ms), measured on this throttled VM and
reported in the output file without a latency claim. H3's
published verdict is unchanged by this amendment, as registered;
the server evidence its caveat asked for now exists.

## D16: Note on the proposed recall-threshold arm (2026-11-17, not run)

A gap-closure brief proposed running "the recall-threshold arm
from ROADMAP (D1)" if it was small and fully specified in the
record. It was not run, for reasons checked against the record
itself: there is no ROADMAP.md file in this repo (the roadmap is
the Deep-pass list inside REPORT.md, "Next steps"), and no item
in that list, and no decision in this file, specifies a
recall-threshold arm. D1 of this file is the corpus decision
(SQuAD v1.1), not an arm. The closest item is Deep step 2,
matched-recall Pareto curves (breadth swept per backend, recall,
p95 and p99 reported at recall 0.90, 0.95 and 0.99, five runs per
setting): it is a multi-backend sweep, not a small single arm,
and it requires the pgvector backend, which cannot run in the
current environment (no PostgreSQL). Running a reduced version
under this name would invent a specification the record does not
contain. Skipped, and recorded here so the skip is on the record;
the item stays available as Deep step 2 for a run with all three
backends available.
