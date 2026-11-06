import numpy as np

from vectorbench.adapters.faiss_adapter import FaissAdapter
from vectorbench.ground_truth import exact_topk
from vectorbench.metrics import recall_at_k


def _data(rng, n=200, d=32):
    vecs = rng.standard_normal((n, d)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ids = list(range(n))
    payloads = [
        {"tenant": "t0" if i % 2 == 0 else "t1", "article": f"A{i % 5}"}
        for i in ids
    ]
    return ids, vecs, payloads


def _adapter(rng):
    ids, vecs, payloads = _data(rng)
    ad = FaissAdapter(dim=vecs.shape[1], m=16, ef_construction=100)
    ad.build(ids, vecs, payloads)
    return ad, ids, vecs


def test_faiss_filter_returns_only_matching():
    rng = np.random.default_rng(3)
    ad, _ids, vecs = _adapter(rng)
    ad.set_breadth(200)
    out = ad.search(vecs[0], 10, ("tenant", "t1"))
    assert out
    assert all(ad.tenants[ad.pos_of[o]] == "t1" for o in out)


def test_faiss_delete_raw_vs_bookkeeping():
    rng = np.random.default_rng(4)
    ad, _ids, vecs = _adapter(rng)
    ad.set_breadth(200)
    victim = ad.search(vecs[10], 1)[0]
    ad.delete([victim])
    # Raw arm: the deleted id can still return.
    raw = ad.search(vecs[10], 5)
    assert victim in raw
    # Bookkeeping arm: the exclusion selector removes it.
    ad.bookkeeping = True
    kept = ad.search(vecs[10], 5)
    assert victim not in kept


def test_faiss_high_recall_at_high_breadth():
    rng = np.random.default_rng(5)
    ad, _ids, vecs = _adapter(rng)
    queries = vecs[:20] + rng.standard_normal(vecs[:20].shape).astype(np.float32) * 0.01
    queries = queries / np.linalg.norm(queries, axis=1, keepdims=True)
    gt = exact_topk(vecs, queries, 10)
    ad.set_breadth(256)
    returned = [ad.search(q, 10) for q in queries]
    assert recall_at_k(returned, gt, 10) >= 0.95
