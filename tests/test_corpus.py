from vectorbench.corpus import (
    TENANT_PROBS,
    build_corpus,
    chunk_words,
    pick_article_group,
    selectivity,
)


def test_chunk_words_windows_and_remainder():
    text = " ".join(f"w{i}" for i in range(95))
    chunks = chunk_words(text, 40)
    assert [len(c.split()) for c in chunks] == [40, 55]  # remainder 15 merged (< half of 40? no: 15 < 20, merged)
    assert chunk_words("one two three", 40) == ["one two three"]
    assert chunk_words("", 40) == []


def test_chunk_words_large_remainder_becomes_chunk():
    text = " ".join(f"w{i}" for i in range(105))
    chunks = chunk_words(text, 40)
    assert [len(c.split()) for c in chunks] == [40, 40, 25]


def _fake_squad(n_articles=4, paras_per=6, qas_per=2):
    data = []
    for a in range(n_articles):
        paras = []
        for p in range(paras_per):
            context = " ".join(f"a{a}p{p}w{i}" for i in range(90))
            qas = [
                {"question": f"question a{a} p{p} q{q}?", "answers": []}
                for q in range(qas_per)
            ]
            paras.append({"context": context, "qas": qas})
        data.append({"title": f"Article{a}", "paragraphs": paras})
    return {"data": data}


def test_build_corpus_split_and_metadata():
    corpus = build_corpus(_fake_squad(), window=40)
    total_paras = 4 * 6
    assert corpus.n_paragraphs + corpus.n_heldout_paragraphs == total_paras
    assert corpus.n_heldout_paragraphs == total_paras // 5
    corpus_puids = {c.paragraph_uid for c in corpus.chunks}
    heldout_puids = {c.paragraph_uid for c in corpus.heldout_chunks}
    assert corpus_puids.isdisjoint(heldout_puids)
    assert all(c.tenant for c in corpus.chunks)
    ids = [c.id for c in corpus.chunks] + [c.id for c in corpus.heldout_chunks]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    # Questions only reference corpus paragraphs.
    assert all(q["paragraph_uid"] in corpus_puids for q in corpus.questions)


def test_tenant_probs_sum_to_one():
    assert abs(sum(TENANT_PROBS) - 1.0) < 1e-9


def test_selectivity():
    assert selectivity(["a", "b", "a", "c"], {"a"}) == 0.5
    assert selectivity([], {"a"}) == 0.0


def test_pick_article_group_near_target():
    squad = _fake_squad(n_articles=10, paras_per=4)
    corpus = build_corpus(squad, window=40)
    group = pick_article_group(corpus.chunks, 0.25)
    share = selectivity([c.article for c in corpus.chunks], set(group))
    assert 0.1 <= share <= 0.45
