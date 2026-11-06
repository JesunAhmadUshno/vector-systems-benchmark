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
rerun is the first item of the Deep pass (ROADMAP.md).

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
result-driven. SPEC.md carries the matching amendment note. The client
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
