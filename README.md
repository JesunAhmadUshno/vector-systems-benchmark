# Vector Systems Benchmark

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

VERDICT_PLACEHOLDER

## Headline results

RESULTS_TABLE_PLACEHOLDER

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
  Qdrant (embedded local mode, payload index before ingestion, native
  Query API hybrid), and pgvector (HNSW, SQL filters, iterative scan
  arms, SQL hybrid) implementations.
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
  filtered recall is a floor. A server-mode rerun is ROADMAP item 1.
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
