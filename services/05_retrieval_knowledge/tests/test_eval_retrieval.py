"""The retrieval eval: golden files that fit the knowledge base, metrics, a full run."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.kb.documents import doc_id_matches
from app.kb.store import KnowledgeStore
from app.kb.trivia import load_trivia_documents
from app.search.aliases import load_alias_file
from app.search.hybrid import Searcher
from scripts.eval_retrieval import (
    EVAL_DIR,
    Outcome,
    Query,
    evaluate,
    first_rank,
    load_live_documents,
    load_queries,
    percentile,
    prepare_index,
    summarize,
    sweep_min_vector_score,
)
from tests.conftest import TEST_DATA
from tests.fakes import FakeEmbedder
from tests.samples import SAMPLE_DOCUMENTS

TRIVIA_FILE = Path(__file__).parents[1] / "data" / "football_trivia_qa.txt"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[KnowledgeStore]:
    s = KnowledgeStore(str(tmp_path / "kb.sqlite"))
    yield s
    s.close()


def test_first_rank_counts_documents_not_chunks() -> None:
    # Two chunks of the same document take one rank.
    assert first_rank(["a", "a", "b", "c"], frozenset({"c"})) == 3
    assert first_rank(["a", "b"], frozenset({"x"})) is None


def test_summary_metrics() -> None:
    q = Query("match", "match", "gm01", "q", None, {}, frozenset({"d"}))
    outcomes = [
        Outcome(q, "hybrid", 1, 10.0),
        Outcome(q, "hybrid", 3, 20.0),
        Outcome(q, "hybrid", None, 30.0),
        Outcome(q, "hybrid", 6, 40.0),
    ]
    [row] = summarize(outcomes)
    assert (row["set"], row["variant"], row["mode"], row["n"]) == ("match", "match", "hybrid", 4)
    assert row["hit@1"] == 0.25
    assert row["hit@5"] == 0.5
    assert row["mrr"] == pytest.approx((1 + 1 / 3 + 0 + 1 / 6) / 4)
    assert row["p50_ms"] == 25.0


def test_percentile() -> None:
    assert percentile([10.0, 20.0, 30.0, 40.0], 95) == pytest.approx(38.5)
    assert percentile([5.0], 50) == 5.0


def test_golden_files_fit_the_knowledge_base() -> None:
    trivia_ids = {d.doc_id for d in load_trivia_documents(str(TRIVIA_FILE))[0]}
    live = load_live_documents(EVAL_DIR)
    live_ids = {d.doc_id for d in live}
    assert all(doc_id_matches(d.category, d.doc_id) for d in live)
    queries = load_queries(EVAL_DIR)
    by_set: dict[str, list[Query]] = {}
    for query in queries:
        by_set.setdefault(query.set, []).append(query)
    assert len({q.id for q in by_set["trivia"]}) == 60
    assert len(by_set["match"]) == 20
    assert len(by_set["out_of_kb"]) == 10
    for query in by_set["trivia"]:
        assert query.expected <= trivia_ids
    for query in by_set["match"]:
        assert query.expected and query.expected <= live_ids
    assert all(not q.expected for q in by_set["out_of_kb"])


def test_the_live_fixture_is_marked_synthetic() -> None:
    data = json.loads((EVAL_DIR / "fixtures" / "live_docs.json").read_text(encoding="utf-8"))
    assert data["synthetic"] is True


async def test_a_full_run_on_a_small_knowledge_base(store: KnowledgeStore) -> None:
    embedder = FakeEmbedder()
    index = await prepare_index(
        store, embedder, [*SAMPLE_DOCUMENTS, *load_live_documents(EVAL_DIR)]
    )
    snapshot = index.snapshot
    assert snapshot is not None
    searcher = Searcher(
        embedder,
        load_alias_file(str(TEST_DATA / "team_aliases.json")),
        reranker=None,
        candidate_k=20,
        rrf_k=60,
        min_vector_score=0.0,
    )
    queries = [q for q in load_queries(EVAL_DIR) if q.set in ("match", "out_of_kb")]
    outcomes = evaluate(searcher, snapshot, queries, modes=("bm25", "hybrid"))
    rows = summarize(outcomes)
    assert {(r["set"], r["mode"]) for r in rows} == {("match", "bm25"), ("match", "hybrid")}
    hybrid = next(r for r in rows if r["mode"] == "hybrid")
    assert hybrid["n"] == 20
    assert hybrid["hit@5"] >= 0.8  # the filters alone narrow most questions to their document

    sweep = sweep_min_vector_score(searcher, embedder, snapshot, queries, [0.0, 0.5, 1.01])
    assert [s["threshold"] for s in sweep] == [0.0, 0.5, 1.01]
    assert sweep[0]["in_kb_lost"] == 0.0
    assert sweep[-1]["out_of_kb_empty_vector"] == 1.0
    assert 0.0 <= sweep[-1]["out_of_kb_empty_hybrid"] <= 1.0
