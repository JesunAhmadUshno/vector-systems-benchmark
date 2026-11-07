# Audit

## Claim audit

- Every number in README.md and RESULTS.md comes from the JSON files in
  results/, produced by run_benchmark.py and rendered by
  generate_results.py. No hand-typed measurements.
- Vendor claims appear only in RESEARCH.md, labelled as vendor evidence,
  and are never used as results.
- The headline claim (the regime map summary in README.md) was checked
  with the Jev claim_check gate before publication. The route returned by
  the gate is recorded in the run log of this audit: see "Jev gate"
  below.
- Novelty is claimed only as a measurement contribution (no primary
  source compares these three systems under this controlled setup, per
  the literature search in RESEARCH.md), never as a new algorithm.

## Run integrity

- Qdrant storage amendment (DECISIONS.md D8): the on-disk local store
  ingested about 1,000 points per minute on this VM (measured in its
  own store file), so the study uses the in-memory variant of the same
  local engine. Decided and committed before any Qdrant number existed.
- Lost run (DECISIONS.md D9): a VM reboot destroyed the first full
  Qdrant run about 60 minutes in, before it wrote results. No number
  from that attempt appears anywhere. The runner now checkpoints after
  every phase.
- Reduced Qdrant protocol (DECISIONS.md D10): the second full-protocol
  attempt passed 60 minutes without finishing its main cells (local
  mode costs about a second per query at 58,999 points; the client
  warns against local mode above 20,000 points). Qdrant was then run
  at 100 queries and 2 repetitions, decided and committed before that
  run started. results_qdrant/env.json records the smaller sample next
  to the main results/env.json.
- The pgvector run shared the VM with the first (lost) Qdrant attempt
  for part of its duration. Its latency percentiles may be inflated by
  that contention; its recall and shortfall numbers are not affected
  by contention. The direction of the possible bias is stated here
  rather than corrected after the fact.
- Local mode warnings, captured verbatim in the run logs: "Payload
  indexes have no effect in the local Qdrant" and "Local mode performs
  exact (brute-force) search, so search_params has no effect". Both
  warnings shape how the Qdrant rows may be read, and RESULTS.md
  carries the same caveat in the H3 evidence.

## Jev gate

- Gate: claim_check on the headline results claim (the regime map
  summary: no universal winner; FAISS fastest unfiltered and weakest
  in the tight cell; the pgvector trap measured at about 12 percent
  selectivity, not at 1 percent; Qdrant local mode exact by
  construction). All arithmetic in the claim was computed in code from
  results/cells.json before the call.
- Model returned: jev-1.13.0. Question id: supported. Noul: 0.47.
- Route: REVIEW (standing bands for claim_check: clear at 0.85 or
  above, block at 0.10 or below, review between). Usage: 850 input
  tokens, 20 output tokens. Spec and result files are kept in the
  programme's Jev log (workspace/tools/jev/, named
  vector-systems-benchmark-claim-spec-2026-11-06.json and
  vector-systems-benchmark-claim-results-2026-11-06.json). No key and
  no full state text are recorded in this repository.
- Review action taken: the claim was re-audited clause by clause
  against results/cells.json. Every number matches the generated file.
  The one clause that goes beyond direct measurement is the planner
  mechanism for the missing trap at 1 percent selectivity; the README
  verdict now attributes that mechanism to the research pack's row 10
  and states the measured values (mean returned 10.00 against a model
  prediction of about 0.42, ef_search 40 times selectivity 0.0105) as the evidence. The claim stands with that
  softening; the gate did not clear it, and this audit does not round
  the route up.

## Data audit

- Corpus: SQuAD v1.1 training paragraphs, CC BY-SA 4.0. The derived
  corpus (chunks, metadata, embeddings) is a local cache in data/, not
  redistributed by this repository. The repository ships code, the
  study design, and the measured results.
- Questions used in the hybrid cell are SQuAD questions; relevance is
  derived from the dataset's own paragraph structure, not from human
  labels collected for this study.
- No personal data. SQuAD is built from Wikipedia articles.

## Licence audit

- Code: Apache-2.0 (LICENSE).
- Corpus licence CC BY-SA 4.0 (attribution: Stanford Question Answering
  Dataset, Rajpurkar et al., 2016).
- Embedding model minishlab/potion-base-8M: MIT.
- FAISS: MIT. Qdrant client: Apache-2.0. pgvector: PostgreSQL License.
  PostgreSQL: PostgreSQL License. model2vec: MIT.

## Cost audit

- Spend: zero. All software is open source; all data is public; the
  study ran on one local VM. No cloud services, no paid APIs, no new
  credentials.

## Security audit

- The benchmark harness opens no network listeners except a local
  PostgreSQL connection over the Unix socket; Qdrant runs embedded in
  memory in the same process. The corpus download is a single HTTPS
  fetch of a public dataset.
- No secrets are used or stored by this repository.

## Grade

Build grade on the house 10,000 scale: 7,300. Deductions are floored
and itemized; nothing is rounded up.

- Qdrant server product not measured: local mode is exact by
  construction, so the Qdrant recall column cannot evidence the
  deployed product's filtered search. Minus 700.
- Qdrant protocol asymmetry (D10): 100 queries and 2 repetitions
  against 300 and 3 for the other backends; latency tails less stable.
  Minus 300.
- Single corpus, single embedding model, single chunk size, one scale
  (58,999 chunks): regime boundaries may move with any of them.
  Minus 300.
- Latency compares three client shapes (in-process, SQL over a socket,
  embedded Python), so it ranks deployed shapes, not index algorithms.
  Minus 250.
- Hybrid limits: no paired significance test, and the pgvector lexical
  arm is PostgreSQL full-text search rather than the shared BM25, so
  its hybrid gain is not encoder-controlled. Minus 250.
- Breadth tuned once on the unfiltered cell and frozen by design, so
  there is no matched-recall Pareto frontier; latency is compared at
  unmatched recall points. Minus 200.
- pgvector latency may carry contention from a parallel run (see Run
  integrity); disclosed, not corrected. Minus 150.
- One churn rate (10 percent) and one churn pattern. Minus 150.
- Jev claim_check returned REVIEW (noul 0.47), not clear; the headline
  claim ships on a documented self-audit with one softened clause.
  Minus 150.
- No replication pass: one run per backend, repetitions within the run
  only. Minus 150.
- Memory and build cost per backend not measured (the research pack's
  C1 estimate stays unchecked until the Deep pass). Minus 100.

Total deductions 2,700. The Deep pass (ROADMAP.md) is scoped to close
these items in evidence order.

## Maintenance audit

- Versions are pinned in results/env.json for the published run. The
  study is expected to drift as the three engines release; the harness
  reruns with one command (METHODS.md) and RESULTS.md is regenerated,
  never edited.
- Known weak points, in order: Qdrant local mode is not the server
  (ROADMAP item 1), its recall is exact by construction, and its cells
  rest on 100 queries and 2 repetitions (D10); latency compares three
  different client shapes (in-process FAISS, SQL over a socket,
  embedded Python), so it ranks deployed shapes, not index algorithms;
  BM25 topk is exact but slow in pure Python (about 0.4 s per question
  at this scale), which caps hybrid repetitions; pgvector insert uses
  text literals for vectors, which is simple and adequate at this
  scale only; pgvector latency may carry contention from a parallel
  run (see Run integrity).
