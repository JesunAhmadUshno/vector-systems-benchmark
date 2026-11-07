# Vector Systems Benchmark

Live dashboard: https://jesunahmadushno.github.io/vector-systems-benchmark/

## The problem

Production retrieval rarely runs unfiltered. A RAG system answers inside a
tenant, a permission boundary, a language, a date range. Under those
filters, a vector engine can fail silently: it returns fewer results than
asked, or worse ones, and raises no error. The pgvector documentation
names the failure "overfiltering". For a user of a permission-scoped
assistant, a silent retrieval miss becomes a confident wrong answer. A
deleted document that still appears in results is the same class of harm.

## Purpose

Measure, on one shared corpus of real text and one node, how FAISS,
PostgreSQL with pgvector, and Qdrant behave as three workload variables
change: metadata filter selectivity, update churn, and hybrid (lexical
plus dense) demand. The output is a measured regime map, not a ranking.
Hypotheses were pre-registered before any experiment code was written
(see SPEC.md and HYPOTHESES.md; the git history shows the order).

## Verdict

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
stays unmeasured here (ROADMAP item 1). Under a 10 percent churn cycle,
FAISS without external bookkeeping keeps serving deleted vectors at a
stale rate of 0.113; with bookkeeping, and in pgvector and Qdrant, the
stale rate is 0.000. Hybrid fusion pays where the lexical arm is the
shared BM25 encoder (FAISS +0.047 nDCG@10; Qdrant native RRF +0.069)
and barely where it is PostgreSQL full-text search (+0.017).

## Headline results

| Backend | Unfiltered recall@10 | Unfiltered p95 ms | Tight filter recall@10 | Tight shortfall | Post-churn recall drop | Hybrid nDCG@10 (dense to hybrid) |
|---|---|---|---|---|---|---|
| faiss | 0.967 | 0.47 | 0.413 | 0.267 | 0.009 | 0.374 to 0.421 |
| pgvector | 0.978 | 3.05 | 1.000 | 0.000 | 0.002 | 0.375 to 0.392 |
| qdrant | 1.000 | 299.53 | 1.000 | 0.000 | 0.000 | 0.387 to 0.456 |

Full generated results, including the trap cell, the churn cells, the
tuning ladders, and the per-hypothesis evidence: RESULTS.md.

## Architecture

One Python harness (src/vectorbench) with three adapters behind one
interface (build, search with a filter spec, delete, insert):

- corpus.py builds the corpus from SQuAD v1.1 (CC BY-SA 4.0): paragraphs
  are chunked into 30-word windows, each chunk labelled with its article
  (a natural, correlated label) and a random tenant (a clean selectivity
  ladder at about 50, 10 and 1 percent).
- embed.py produces one embedding set for all backends:
  minishlab/potion-base-8M via model2vec (MIT), 256 dimensions.
- ground_truth.py computes exact brute-force top 10 with NumPy. Every
  recall number is measured against it.
- bm25.py is the shared sparse encoder for every hybrid arm, so hybrid
  differences cannot come from the encoder. Fusion is RRF, k = 60.
- adapters/ holds the FAISS (IndexHNSWFlat with IDSelector filtering),
  Qdrant (embedded local mode, in-memory variant per DECISIONS.md D8,
  native Query API hybrid; payload index calls are kept for server
  parity and have no effect in local mode), and pgvector (HNSW, SQL
  filters, iterative scan arms, SQL hybrid) implementations.
- run_benchmark.py runs the cells and writes results/*.json.
  generate_results.py renders RESULTS.md and the table above from those
  files. No number is typed by hand.

## Reproduce

```
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest tests/
python -m vectorbench.run_benchmark --backends faiss,qdrant,pgvector
python -m vectorbench.generate_results
```

The pgvector arm needs a local PostgreSQL with the pgvector extension
and a database named vsbench (see AUDIT.md for the setup used here).
Corpus and embeddings are cached in data/ on first run (about 59k
chunks). One command reruns the whole study; RESULTS.md is regenerated,
never edited.

## Limitations

- Single node, CPU only, corpus fits in RAM. Nothing here speaks about
  clusters, GPUs, or billion-scale data.
- Qdrant runs in embedded local mode, a Python implementation, not the
  production server. Its latency is not the server's latency, and its
  filtered recall is exact by construction, so it cannot evidence the
  server product's filtered recall at all. A server-mode rerun is
  ROADMAP item 1.
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

## Files

- SPEC.md: the pre-registered study design.
- HYPOTHESES.md: H1 to H6 with thresholds and falsification rules.
- RESEARCH.md: the literature base, with vendor claims labelled.
- METHODS.md: formulas, controls, sample sizes, threats to validity.
- RESULTS.md: generated results and hypothesis verdicts.
- AUDIT.md: claim, data, licence, cost and security audit, and the Jev
  gate record.
- DECISIONS.md: corpus, model and configuration decisions with reasons.
- ROADMAP.md: the Deep pass, in evidence order.
- docs/research-review.md: the study graded against a research rubric,
  with each remaining gap and the compute it needs.
- site/: the live dashboard, built from results/ by .github/workflows/pages.yml.

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
