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

## Jev gate

- Gate: claim_check on the headline results claim.
- Route: recorded here after the run, with model version and question
  id, in the programme's results log. Bands: clear at 0.85 or above,
  block at 0.10 or below, review between.

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
  PostgreSQL connection over the Unix socket and the embedded Qdrant
  store on disk. The corpus download is a single HTTPS fetch of a
  public dataset.
- No secrets are used or stored by this repository.

## Maintenance audit

- Versions are pinned in results/env.json for the published run. The
  study is expected to drift as the three engines release; the harness
  reruns with one command (METHODS.md) and RESULTS.md is regenerated,
  never edited.
- Known weak points, in order: Qdrant local mode is not the server
  (ROADMAP item 1); BM25 topk is exact but slow in pure Python (about
  0.4 s per question at this scale), which caps hybrid repetitions;
  pgvector insert uses text literals for vectors, which is simple and
  adequate at this scale only.
