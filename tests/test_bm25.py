from vectorbench.bm25 import BM25, tokenize


def test_tokenize():
    assert tokenize("The Cat, sat! 42") == ["the", "cat", "sat", "42"]


def _tiny():
    texts = [
        "the cat sat on the mat",
        "dogs chase cats in the park",
        "quantum vectors encode semantic meaning",
    ]
    return BM25().fit(texts)


def test_bm25_ranks_matching_doc_first():
    bm = _tiny()
    assert bm.topk("cat", 1) == [0]
    assert bm.topk("quantum vectors", 1) == [2]


def test_bm25_idf_positive_and_sparse_roundtrip():
    bm = _tiny()
    assert all(v > 0 for v in bm.idf.values())
    idx, vals = bm.doc_sparse(0)
    assert len(idx) == len(vals) > 0
    assert all(i in bm.vocab.values() for i in idx)
    q_idx, q_vals = bm.query_sparse("cat sat")
    assert len(q_idx) == len(q_vals) == 2


def test_bm25_topk_respects_allowed():
    bm = _tiny()
    assert bm.topk("quantum", 3, allowed={2}) == [2]
    assert bm.topk("the", 3, allowed={1}) == [1]
    assert bm.topk("the", 3, allowed={2}) == []
