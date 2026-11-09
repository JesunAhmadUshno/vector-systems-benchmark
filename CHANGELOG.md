# Changelog

All notable changes to this project. Format: Keep a Changelog 1.1.
Versions follow Semantic Versioning; no release is tagged yet.

## [Unreleased]

### Changed
- 2026-11-08: Adopted the portfolio standard v2. README opens with the
  question, headline, field, job family and verdict (Functional).
  REPORT.md is the report: it takes the old README narrative, the
  hypothesis scoring with misses, the audit's itemized limitations, the
  research review (docs/research-review.md) and the Deep-pass list
  (ROADMAP.md). Grades and rubric marks left the public repo (grades are
  internal); the site's limitations panel now lists them without points.
- 2026-11-08: SPEC.md restored byte for byte to its locked text of
  838e6da; the in-place amendment note moved to DECISIONS.md D12. The
  lock is tagged proposal-v1 on 838e6da and tests/test_layout.py pins
  the SHA-256 of SPEC.md and HYPOTHESES.md.
- 2026-11-08: CI runs with read-only token permissions, checks that
  RESULTS.md regenerates unchanged from results/, and builds the site.
  CodeQL (Python, JavaScript) and Dependabot added; main protected.

### Added
- 2026-11-07: Live dashboard in site/ and its Pages workflow; research
  review (now in REPORT.md).
- 2026-11-07: Sample sizes, Wilson intervals and the disclosed H2 cell
  set (DECISIONS.md D11) in the generated results; tests for the
  verdict and C2 logic. C2 prediction corrected to 0.42.
- 2026-11-06: Full three-backend results (FAISS, pgvector, Qdrant in
  embedded local mode under D8 to D10).
- 2026-11-06: The harness: corpus, embeddings, three adapters, tests.
- 2026-11-06: Pre-registration, SPEC.md and HYPOTHESES.md (838e6da),
  before any experiment code.
