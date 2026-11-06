"""Corpus construction from SQuAD v1.1.

The corpus is built once and cached as JSONL plus a metadata JSON. The
build is deterministic: every random choice takes an explicit seed.

Layout decisions (pre-registered in SPEC.md):
- Paragraphs are split into corpus and held-out sets by a seeded shuffle
  (80 / 20). Held-out paragraphs never enter any index.
- Corpus paragraphs are chunked into fixed word windows.
- Each chunk gets an `article` label (its SQuAD article title) and a
  `tenant` label drawn from a fixed skewed distribution.
- Held-out chunks serve two roles: query vectors for the recall cells,
  and fresh inserts for the churn cell.
- Questions on corpus paragraphs are the hybrid query set. A chunk is
  relevant to a question when it comes from the question's paragraph.
"""

from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SQUAD_URL = "https://rajpurkar.github.io/SQuAD-explorer/dataset/train-v1.1.json"
SQUAD_LICENCE = "CC BY-SA 4.0"

TENANT_PROBS = [0.49, 0.30, 0.12, 0.05, 0.025, 0.01, 0.005]
TENANT_NAMES = [f"t{i}" for i in range(len(TENANT_PROBS))]

SPLIT_SEED = 13
TENANT_SEED = 42
CHURN_SEED = 7
QUERY_SEED = 99


@dataclass
class Chunk:
    id: int
    text: str
    article: str
    paragraph_uid: int
    tenant: str = ""


@dataclass
class Corpus:
    chunks: list[Chunk] = field(default_factory=list)          # indexed set
    heldout_chunks: list[Chunk] = field(default_factory=list)  # queries + inserts
    questions: list[dict] = field(default_factory=list)        # hybrid queries
    window_words: int = 40
    n_paragraphs: int = 0
    n_heldout_paragraphs: int = 0


def download_squad(cache_path: Path) -> dict:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        urllib.request.urlretrieve(SQUAD_URL, cache_path)
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def chunk_words(text: str, window: int) -> list[str]:
    """Split text into non-overlapping word windows of `window` words.

    A trailing remainder shorter than half a window is merged into the
    last full window; a paragraph shorter than one window yields one chunk.
    """
    words = text.split()
    if not words:
        return []
    if len(words) <= window:
        return [" ".join(words)]
    chunks = [" ".join(words[i:i + window]) for i in range(0, len(words) - window + 1, window)]
    remainder = len(words) % window
    if remainder:
        tail = " ".join(words[len(words) - remainder:])
        if remainder < window // 2:
            chunks[-1] = chunks[-1] + " " + tail
        else:
            chunks.append(tail)
    return chunks


def build_corpus(squad: dict, window: int = 40) -> Corpus:
    paragraphs: list[dict] = []
    uid = 0
    for article in squad["data"]:
        title = article["title"]
        for para in article["paragraphs"]:
            paragraphs.append(
                {
                    "uid": uid,
                    "article": title,
                    "context": para["context"],
                    "qas": para.get("qas", []),
                }
            )
            uid += 1

    rng = random.Random(SPLIT_SEED)
    order = list(range(len(paragraphs)))
    rng.shuffle(order)
    n_holdout = len(paragraphs) // 5
    holdout_uids = set(order[:n_holdout])
    corpus_paras = [p for p in paragraphs if p["uid"] not in holdout_uids]
    holdout_paras = [p for p in paragraphs if p["uid"] in holdout_uids]

    tenant_rng = random.Random(TENANT_SEED)

    def make_chunks(paras: list[dict], start_id: int, with_tenant: bool) -> list[Chunk]:
        out: list[Chunk] = []
        cid = start_id
        for para in paras:
            for piece in chunk_words(para["context"], window):
                chunk = Chunk(id=cid, text=piece, article=para["article"], paragraph_uid=para["uid"])
                if with_tenant:
                    chunk.tenant = tenant_rng.choices(TENANT_NAMES, weights=TENANT_PROBS, k=1)[0]
                out.append(chunk)
                cid += 1
        return out

    chunks = make_chunks(corpus_paras, 0, with_tenant=True)
    heldout = make_chunks(holdout_paras, len(chunks), with_tenant=False)

    questions: list[dict] = []
    for para in corpus_paras:
        for qa in para["qas"]:
            questions.append(
                {
                    "question": qa["question"],
                    "paragraph_uid": para["uid"],
                    "article": para["article"],
                }
            )

    return Corpus(
        chunks=chunks,
        heldout_chunks=heldout,
        questions=questions,
        window_words=window,
        n_paragraphs=len(corpus_paras),
        n_heldout_paragraphs=len(holdout_paras),
    )


def selectivity(values: list[str], wanted: set[str]) -> float:
    """Measured share of items whose value is in `wanted`."""
    if not values:
        return 0.0
    return sum(1 for v in values if v in wanted) / len(values)


def pick_article_group(chunks: list[Chunk], target_share: float) -> list[str]:
    """Pick a set of articles whose combined chunk share is closest to target.

    Articles are sorted by chunk count, largest first, and added greedily
    until adding the next article would move the share further from the
    target. Deterministic.
    """
    counts: dict[str, int] = {}
    for c in chunks:
        counts[c.article] = counts.get(c.article, 0) + 1
    total = len(chunks)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    chosen: list[str] = []
    share = 0.0
    for name, cnt in ranked:
        new_share = share + cnt / total
        if abs(new_share - target_share) <= abs(share - target_share):
            chosen.append(name)
            share = new_share
        if share >= target_share:
            break
    return chosen
