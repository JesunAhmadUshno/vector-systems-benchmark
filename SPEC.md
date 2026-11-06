# Study Specification: Vector Systems Benchmark

Status: pre-registered. This file and HYPOTHESES.md are committed before any
experiment code is written. Git history is the proof of order.

## Research question

On one node, with free software and one shared corpus of real text, how do
FAISS, PostgreSQL with pgvector, and Qdrant compare on recall, latency,
filtered recall, freshness under churn, and hybrid search quality, as three
workload variables change:

1. Metadata filter selectivity (the share of the corpus a filter admits).
2. Update churn (deletes and inserts after the index is built).
3. Hybrid demand (queries that need lexical and dense signals together).

The deliverable is a measured regime map, not a winner. The claim tested is
that each system wins in a different regime, and that the boundaries of those
regimes can be measured.

## Why it matters

Most production retrieval runs under constraints: tenant, permission, date,
language. These are filtered queries. A filtered query can fail silently: the
engine returns fewer or worse results and raises no error. The pgvector
documentation names this failure "overfiltering". For a user of a
permission-scoped assistant, a silent retrieval miss becomes a confident
wrong answer. A deleted or retracted document that still appears in results
is the same class of harm. This study measures when each engine loses recall
silently, so builders can protect those users.

## Corpus

- Source: SQuAD v1.1 training set paragraphs (Stanford Question Answering
  Dataset). Licence: CC BY-SA 4.0. Source URL is recorded in METHODS.md.
- Unit: fixed-size word-window chunks of the paragraphs, no overlap. Target
  size is set by a parameter (default target 60,000 chunks). The exact chunk
  count produced is recorded in results/env.json.
- Each chunk carries two metadata fields:
  - `article`: the SQuAD article title the paragraph came from. This label
    is correlated with vector position, because chunks of one article are
    about one topic. It models natural labels.
  - `tenant`: a random label drawn from a fixed skewed distribution with a
    fixed seed (shares about 49, 30, 12, 5, 2.5, 1, 0.5 percent). This
    label is independent of vector position. It gives a clean selectivity
    ladder.
- A held-out set of paragraphs (fixed seed split) is never indexed. Its
  chunks are the query vectors for the recall and latency cells.
- SQuAD questions whose paragraphs are in the held-out split are not used.
  SQuAD questions on indexed paragraphs are the relevance queries for the
  hybrid cell. A chunk is relevant to a question if it comes from the
  question's own paragraph.

## Embeddings

- Dense: minishlab/potion-base-8M through the model2vec library (model
  licence MIT). Dimension 256. The same embeddings are fed to all three
  backends. Embeddings are L2-normalized; distance is cosine, computed as
  inner product on normalized vectors in every backend.
- Sparse: one shared BM25 implementation in this repository, used for every
  backend's hybrid arm, so encoder differences cannot explain hybrid
  differences. Fusion is reciprocal rank fusion (RRF) with k = 60, fixed.

## Backends and configurations

- FAISS (faiss-cpu): IndexHNSWFlat, M = 32, efConstruction = 200. Filtering
  uses IDSelectorBatch at search time. Deletes are handled two ways, both
  measured: no bookkeeping (raw index, deleted ids can return) and an
  exclusion selector over the deleted id set.
- Qdrant (qdrant-client, embedded local mode on disk): one collection,
  cosine distance, HNSW M = 32, efConstruct = 200. Payload indexes on
  `tenant` and `article` are created before ingestion, so filter-aware
  graph edges can be built (see the research pack, row 14). Hybrid uses
  native sparse plus dense vectors with RRF fusion in the Query API.
- pgvector: PostgreSQL with the pgvector extension, HNSW index
  (m = 32, ef_construction = 200), cosine distance. Filtering is a SQL
  WHERE clause on indexed metadata columns. Hybrid combines tsvector
  full-text ranking with vector ranking by RRF in SQL. Two filter
  configurations are measured: iterative scan off with the default
  hnsw.ef_search = 40 (the trap cell), and iterative scan on
  (hnsw.iterative_scan = relaxed_order, hnsw.max_scan_tuples = 20000).
- Operating point: for the main cells, each backend's search breadth
  parameter (efSearch, hnsw_ef, hnsw.ef_search) is tuned once on the
  unfiltered cell to reach recall@10 at or above 0.95, then frozen for all
  cells. The tuned values are recorded in results/env.json. The pgvector
  trap cell is measured separately at defaults, on purpose, because
  defaults are what an untuned deployment runs.

## Regime cells

For every backend, on the same corpus and the same queries:

1. Unfiltered: recall@10, p50 and p95 latency.
2. Random-label filter at about 50 percent selectivity (tenant share).
3. Random-label filter at about 10 percent selectivity.
4. Random-label filter at about 1 percent selectivity (the tight cell).
5. Correlated-label filter at about 1 percent selectivity (article group).
6. Churn: after cells 1 to 5, delete a fixed random 10 percent of points
   and insert an equal number of fresh held-out chunks. Re-measure recall,
   latency, and the stale-result rate (share of returned ids that were
   deleted) on the unfiltered and the 1 percent cells.
7. Hybrid: on the SQuAD question set, nDCG@10 and recall@100 for BM25
   alone, dense alone, and hybrid RRF, per backend where the backend
   supports the arm natively or through the shared fusion code. Arms that
   a backend cannot run are marked not supported, never estimated.

## Ground truth and metrics

- Ground truth for recall cells is exact brute-force search over the live
  (non-deleted) corpus, computed with NumPy and cached to disk. Recall@10
  is the mean over queries of |returned top 10 intersect exact top 10| / 10.
- For filtered cells, ground truth is exact search inside the filtered
  subset only.
- A second filtered metric, shortfall rate, counts queries where the
  backend returned fewer than 10 results. This is the user-visible form of
  overfiltering.
- Latency is wall time per query measured in the client process, in
  milliseconds, reported as p50 and p95 over all queries in the cell.
  Latency includes client and serialization cost. FAISS runs in process;
  Qdrant local mode and pgvector run through their clients. This asymmetry
  is a named limitation, not a hidden one.
- Churn freshness: stale-result rate as defined above, plus recall change
  from the pre-churn cell.
- Hybrid: nDCG@10 with graded relevance 1 for chunks of the question's
  paragraph, 0 otherwise. recall@100 the same way at depth 100.
- Every number in RESULTS.md and in the README table is written by a
  generator script from files in results/. No number is typed by hand.

## Repetitions and uncertainty

- Each recall and latency cell runs the full query set 3 times. Recall is
  reported for run 1 and checked for stability across runs (recall of a
  fixed index is deterministic; any drift is reported). Latency is
  reported as the median run's percentiles, with the spread across runs in
  the results file.
- Query set sizes: at least 300 held-out queries for recall cells, at
  least 200 questions for the hybrid cell. Exact counts are recorded.

## Scope limits (named before results exist)

- Single node, CPU only, corpus fits in RAM. Nothing here speaks about
  clusters, GPUs, or billion-scale data.
- One corpus, one embedding model, one chunking. A different corpus can
  move the regime boundaries.
- Qdrant runs in embedded local mode, not as a network server. Its
  latency numbers exclude network cost, which favours it against a real
  deployment and is stated wherever its latency is quoted.
- pgvector iterative scan behaviour is version specific. Versions are
  pinned and recorded in results/env.json.

## Failure handling

If a backend cannot be stood up after a real attempt, the harness code for
it ships, its cells are marked blocked with the exact error, and the regime
map is published with the cells it could not fill. No number is ever
estimated for a blocked backend.
