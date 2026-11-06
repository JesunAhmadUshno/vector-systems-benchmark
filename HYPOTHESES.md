# Pre-registered Hypotheses

Committed before any experiment code. Each hypothesis states its threshold
in advance and the rule that falsifies it. Verdict words follow the
programme charter, gate 9: Supported, Partially supported, Refuted,
Inconclusive, Not yet measured.

All recall values are recall@10 against exact brute-force ground truth, as
defined in SPEC.md. Selectivity means the share of the live corpus admitted
by the filter. The tight cell is the random-label filter at about 1 percent
selectivity.

## H1: The pgvector overfiltering trap is real at defaults, and iterative scan closes it

Prediction. With iterative scan off and the default hnsw.ef_search = 40,
pgvector in the tight cell shows a shortfall rate above 0.50 (more than
half of queries return fewer than 10 results) or recall@10 below 0.50.
With iterative scan on (relaxed_order, max_scan_tuples = 20000), the same
cell reaches recall@10 at or above 0.90 and shortfall rate at or below
0.05.

Falsified if: the default cell already reaches recall@10 at or above 0.90
with shortfall at or below 0.05 (no trap), or the iterative-scan cell stays
below 0.90 (the documented fix does not close it here).

Basis: the pgvector documentation's own estimate, checked in the research
pack as calculation C2: expected matches are about ef_search times
selectivity, so 40 times 0.01 gives 0.4 expected matches for k = 10.

## H2: No universal winner

Prediction. Across the measured cells (unfiltered, 50 percent, 10 percent,
1 percent random-label, 1 percent correlated-label, post-churn), no single
backend is best on both recall@10 and p95 latency in every cell. Each
backend leads at least one cell on at least one of the two metrics, or
ties for the lead.

Falsified if: one backend leads every cell on both metrics, or one backend
leads no cell on either metric while another leads all.

## H3: Qdrant filtered recall is stable at the tight cell without per-cell tuning

Prediction. With the payload index created before ingestion and one frozen
search configuration, Qdrant recall@10 in the tight cell is at or above
0.90, and its shortfall rate is 0.

Falsified if: tight-cell recall@10 is below 0.90, or any query returns
fewer than 10 results.

Basis: Qdrant documentation states that filter criteria apply during the
graph search when the payload index exists before the graph is built.
Rows 15 and 16 of the research pack are vendor evidence and are treated as
a claim to test, not as proof.

## H4: FAISS has the lowest latency in the unfiltered cell at matched recall

Prediction. At an operating point where every backend reaches unfiltered
recall@10 at or above 0.95, FAISS p95 latency is the lowest of the three.

Falsified if: any other backend's p95 is lower at a recall at or above
0.95 in the same cell.

Note: FAISS runs in process and the others run through clients, so this
hypothesis tests the deployed shape (library versus service), not only the
index algorithm. That asymmetry is named in SPEC.md as a limitation.

## H5: Churn separates the backends on freshness

Predictions, per backend, after a 10 percent delete and 10 percent insert
cycle:
- pgvector: stale-result rate 0. Deletes are transactional.
- Qdrant: stale-result rate 0. Deletes are tombstones that search skips.
- FAISS HNSW with no bookkeeping: stale-result rate above 0. The graph
  cannot remove points, so deleted ids return unless the caller excludes
  them.
- FAISS HNSW with the exclusion selector: stale-result rate 0.
- All backends: post-churn recall@10 drops by less than 0.05 against the
  pre-churn cell on the same queries.

Falsified per line: any line's measured value crosses its stated bound.

## H6: Hybrid beats dense alone on the question set, with identical encoders

Prediction. On the SQuAD question set, hybrid search (dense plus the
shared BM25, fused with RRF k = 60) reaches nDCG@10 at least 0.02 above
dense alone, for each backend that runs both arms.

Falsified if: the hybrid gain is below 0.02 for a backend that runs both
arms, or hybrid is worse than dense alone.

Note: the sparse encoder and the fusion rule are identical across
backends, so a confirmed gain is a property of the query set and the
fusion, not of an engine. Engine differences in the hybrid cell are
reported as implementation differences only.

## Standing checks (not hypotheses)

- C2 check: the measured mean number of results returned per query in the
  pgvector default tight cell is compared with the C2 prediction of about
  0.4. Agreement or disagreement is reported either way.
- Exactness check: each adapter, run with exact settings on a small fixed
  sample, must reach recall@10 of 1.000 against the NumPy ground truth
  before its approximate numbers are trusted. This is a harness test, not
  a result.
