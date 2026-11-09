# Methods

## Data

- Corpus: SQuAD v1.1 training set (Stanford Question Answering Dataset),
  downloaded from https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v1.1.json
  Licence: CC BY-SA 4.0. Paragraphs are split 80 / 20 into corpus and
  held-out sets by a seeded shuffle (seed 13). Corpus paragraphs are
  chunked into 30-word windows; exact counts are in results/env.json.
- Metadata: `article` is the SQuAD article title (a label correlated with
  vector position). `tenant` is drawn per chunk from a fixed skewed
  distribution (seed 42; designed shares 49, 30, 12, 5, 2.5, 1, 0.5
  percent; measured shares in results/env.json).
- Queries: the first 300 held-out chunks (seed-independent order from the
  split). Hybrid queries: 250 SQuAD questions sampled with seed 99 from
  questions on corpus paragraphs.
- Embeddings: minishlab/potion-base-8M via model2vec (MIT), 256
  dimensions, L2-normalized. One embedding set feeds all backends.

## Controls

- Same corpus, same embeddings, same queries, same ground truth for every
  backend and every cell.
- Each backend's breadth parameter is tuned once on the unfiltered cell
  to the first ladder value reaching recall@10 at or above 0.95 (ladder
  40, 80, 120, 200, 320), then frozen. Tuned values are in RESULTS.md.
- The pgvector trap cells are the one deliberate exception: they run the
  shipped defaults (iterative scan off, ef_search 40), because the
  behaviour of an untuned deployment is the object of study there.
- The sparse encoder (this repo's BM25) and the fusion rule (RRF, k = 60)
  are identical across hybrid arms. The pgvector lexical arm is the one
  named exception: it uses PostgreSQL full-text ranking (ts_rank), the
  native product path, so its lexical scores are not the shared BM25's.

## Formulas

- recall@10 = mean over queries of |returned top 10 intersect exact
  top 10| / 10. Exact top 10 comes from brute-force NumPy search over the
  live set (filtered cells: over the filtered live subset).
- Shortfall rate = share of queries returning fewer than 10 results.
- Mean returned = mean number of results per query.
- Latency = wall time per query in the client process; p50 and p95 over
  the median of 3 repetitions of the full query set.
- Stale rate = share of returned slots, in the post-churn unfiltered
  cell, that hold an id deleted by the churn step.
- nDCG@10 with binary relevance (a chunk is relevant to a question when
  it comes from the question's paragraph); recall@100 analogously.
- RRF score = sum over rankings of 1 / (60 + rank), rank starting at 1.

## Sample sizes and repetitions

- 300 recall queries per cell, 3 repetitions. Recall of a fixed index is
  deterministic in these engines, so repetitions check stability;
  latency uses the median repetition.
- 250 sampled hybrid questions; the number actually scored (questions
  with at least one relevant chunk) is recorded in results/cells.json.
- Churn is one cycle of 10 percent delete plus 10 percent insert. Delete
  set and insert tenants use seeds 7 and 8.

## Threats to validity

- Client asymmetry: FAISS runs in process; pgvector goes through a Unix
  socket to a server; Qdrant runs in embedded local mode, whose internals
  are a Python implementation, not the production Rust server. Latency
  comparisons measure the deployed shape, not only the index. Recall and
  shortfall comparisons are not affected by this asymmetry.
- Local mode Qdrant may not exercise the server's filterable HNSW path;
  its filtered recall is a lower bound on the server's behaviour, and its
  latency is not the server's latency. Both are named wherever quoted.
- One corpus, one embedding model, one chunk size. Regime boundaries can
  move with any of them.
- Tenant labels are random by design (clean selectivity); article labels
  cover the correlated case for one topic structure only.
- pgvector numbers are for the pinned version in results/env.json.
  Iterative scan behaviour is version specific.
- No inferential statistics are claimed beyond the recorded repetitions:
  differences are reported as measured effect sizes, and the verdict
  rules in HYPOTHESES.md use fixed thresholds, not significance tests.
  The hybrid cell reports mean nDCG over the scored questions without a
  paired test; the Deep pass adds one (see REPORT.md, Next steps).

## Reproduction

```
python -m pip install -r requirements.txt
python -m pip install -e .
python -m vectorbench.run_benchmark --backends faiss,qdrant,pgvector
python -m vectorbench.generate_results
```

PostgreSQL with pgvector must be running with a database named vsbench
reachable at the default conninfo in run_benchmark.py (override with
--pg-conninfo). Setup used for the published run is described in
AUDIT.md. The data/ and work/ directories are caches and are not
committed; results/*.json are committed and are the evidence.
