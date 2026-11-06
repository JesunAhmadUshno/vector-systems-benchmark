"""Dense embeddings: minishlab/potion-base-8M through model2vec.

One model for every backend (the P06 pattern). Embeddings are
L2-normalized at creation, so cosine similarity is an inner product in
every backend.
"""

from __future__ import annotations

import numpy as np

MODEL_NAME = "minishlab/potion-base-8M"
MODEL_LICENCE = "MIT"


def embed_texts(texts: list[str], batch_size: int = 1024) -> np.ndarray:
    from model2vec import StaticModel

    model = StaticModel.from_pretrained(MODEL_NAME)
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=False)
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return vectors / norms
