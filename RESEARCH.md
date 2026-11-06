# Research summary

This file condenses the literature base for the study. The full evidence
table, with per-row verification status, is verdict pack 04 of the AI
Platform Research Programme (filed in the programme record). Rows that the
pack marked unverified are treated here as claims to test, not as facts.
Vendor-authored evidence is labelled as vendor evidence.

## The systems

FAISS is a library, not a database: a toolkit of indexing methods for
search, clustering, compression and transformation of vectors (Douze et
al., "The Faiss library", arXiv:2401.08281). Its HNSW index (Malkov and
Yashunin, IEEE TPAMI 42(4), 2020) builds a multi-layer graph with
logarithmic scaling, and cannot remove vectors, because removal would
destroy the graph structure (FAISS wiki). Memory for HNSWFlat is about
4d + 8M bytes per vector, so raw float storage dominates at high dimension
(pack calculation C1, arithmetic verified).

pgvector is a PostgreSQL extension. Filtering is applied after the
approximate index scan, so a selective filter can return too few results;
the documentation's own example: at 10 percent selectivity with the
default ef_search of 40, only about 4 rows match on average (pack
calculation C2). Version 0.8.0 added iterative scans, which keep scanning
until enough results are found or a tuple budget is reached, and relaxed
ordering, which trades exact distance order for recall (pgvector 0.8.0
README). Hybrid search in pgvector is assembled by the user: full-text
search plus vector search, fused in SQL (pgvector README).

Qdrant is a dedicated vector database. Its payload index extends the
HNSW graph, so filter criteria can apply during the search itself, but
the extra filter-aware edges exist only if the graph is built after the
payload index (Qdrant docs). Its query planner chooses among several
strategies, including filterable HNSW and a full scan (Qdrant article,
vendor evidence). Hybrid queries fuse dense and sparse result lists with
RRF or DBSF through the Query API, available since v1.10.0 (Qdrant docs).
Deletes are tombstones, removed later by a vacuum optimizer whose default
trigger is 20 percent deleted in a segment (Qdrant docs; pack calculation
C3 estimates the search overhead this implies at up to 1.25 times the
live points).

## The neighbouring literature

- Filtered-DiskANN (Gollapudi et al., WWW 2023) showed filtered search is
  a distinct problem, an order of magnitude more efficient than prior
  methods on real data with natural labels. It studies an algorithm, not
  these three systems.
- The Big ANN NeurIPS'23 challenge ran filtered, streaming,
  out-of-distribution and sparse tracks (Simhadri et al., NeurIPS 2025
  Datasets and Benchmarks). The streaming track is the model for this
  study's churn cell.
- ANN-Benchmarks (Aumuller, Bernhardsson, Faithfull, Information Systems,
  2020) found that very different k-NN approaches give comparable quality
  and performance trade-offs, and it compares at matched recall. That is
  the methodological standard this study follows: compare at tuned
  operating points, not at defaults, except where the defaults themselves
  are the object of study (the trap cell).
- No primary source compares FAISS, pgvector and Qdrant under one
  controlled setup with filtering and churn as variables. That gap is the
  study's reason to exist. The claim is a measurement contribution, not a
  new algorithm.

## Past, present, future

Past: nearest neighbour search was a library problem; indexes were built
once, queried read-only, and filters were an application concern.

Present: retrieval is a database problem. Production RAG systems filter
by tenant and permission, update continuously, and mix lexical with dense
signals. The three systems in this study are the three shapes that
deployment takes: library, SQL extension, dedicated engine.

Future: filtered and streaming benchmarks are becoming the standard
(Big ANN tracks), and engines are converging on filter-aware graph search
and iterative scanning. Measured regime maps, refreshed per version, are
the durable artefact; any single version's numbers expire.

## Search record

Sources were gathered for verdict pack 04 from primary documentation:
FAISS wiki and paper, pgvector README and 0.8.0 release notes, Qdrant
documentation (indexing, hybrid queries, optimizer) and Qdrant articles
(vendor), plus the papers above. Inclusion rule: a claim enters the
design only from a primary source or is labelled vendor or unverified.
