"""POST /index/upsert, DELETE /index/{doc_id}, GET /index/stats (CONTRACT §6)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import Container
from tests.conftest import assert_problem
from tests.samples import SAMPLE_CHUNK_COUNT

NEW_MATCH: dict[str, Any] = {
    "doc_id": "match-2026-mw06-64-65",
    "title": "Liverpool 3–0 Manchester City · PL 2026/27 นัดที่ 6",
    "text": "Premier League 2026/27, matchweek 6. Liverpool 3-0 Manchester City at Anfield.",
    "category": "match_report",
    "origin": "api-football",
    "season": "2026",
    "matchweek": 6,
    "team_ids": [64, 65],
    "date": "2026-09-27",
    "fetched_at": "2026-09-28T09:00:00+07:00",
    "url": None,
}


def doc(**changes: Any) -> dict[str, Any]:
    return {**NEW_MATCH, **changes}


async def upsert(client: httpx.AsyncClient, *documents: dict[str, Any]) -> httpx.Response:
    return await client.post(
        "/index/upsert", json={"request_id": "req-1", "documents": list(documents)}
    )


async def doc_ids_found(client: httpx.AsyncClient, query: str) -> list[str]:
    response = await client.post("/search", json={"query": query, "top_k": 20})
    return [c["source"]["doc_id"] for c in response.json()["chunks"]]


async def test_upsert_matches_contract_and_is_searchable(client: httpx.AsyncClient) -> None:
    response = await upsert(client, NEW_MATCH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "upserted", "chunks", "index_version"}
    assert (body["request_id"], body["upserted"], body["chunks"]) == ("req-1", 1, 1)
    assert NEW_MATCH["doc_id"] in await doc_ids_found(client, "Liverpool Manchester City Anfield")

    search = await client.post("/search", json={"query": "Anfield"})
    assert search.json()["index_version"] == body["index_version"]


async def test_upserting_the_same_doc_id_keeps_only_the_latest(
    client: httpx.AsyncClient, container: Container
) -> None:
    await upsert(client, NEW_MATCH)
    response = await upsert(client, doc(text="Liverpool 4-0 Manchester City after extra goals."))
    assert response.json()["upserted"] == 1
    snapshot = container.index.snapshot
    assert snapshot is not None
    texts = [r.document.text for r in snapshot.records if r.chunk.doc_id == NEW_MATCH["doc_id"]]
    assert texts == ["Liverpool 4-0 Manchester City after extra goals."]
    stored = [s for s in container.store.load_all() if s.chunk.doc_id == NEW_MATCH["doc_id"]]
    assert [s.document.text for s in stored] == texts


async def test_unchanged_upsert_keeps_the_version(client: httpx.AsyncClient) -> None:
    first = (await upsert(client, NEW_MATCH)).json()
    again = (await upsert(client, NEW_MATCH)).json()
    assert again["index_version"] == first["index_version"]


async def test_request_id_defaults_to_the_header(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/index/upsert", json={"documents": [NEW_MATCH]}, headers={"X-Request-ID": "hdr-9"}
    )
    assert response.json()["request_id"] == "hdr-9"


@pytest.mark.parametrize(
    "document",
    [
        doc(doc_id="match-2026-mw6-64-65"),
        doc(doc_id="standings-2026-mw06"),
        doc(category="news"),
        doc(origin="twitter"),
        doc(text=""),
        doc(text="   "),
        doc(title=""),
        doc(text="Liverpool\u0000"),
        doc(season="26"),
        doc(matchweek=39),
        doc(date="yesterday"),
        doc(colour="red"),
        {k: v for k, v in NEW_MATCH.items() if k != "text"},
    ],
)
async def test_invalid_documents_are_422(
    client: httpx.AsyncClient, container: Container, document: dict[str, Any]
) -> None:
    before = container.index.snapshot
    response = await upsert(client, NEW_MATCH | {"doc_id": "match-2026-mw06-1-2"}, document)
    assert_problem(response, 422, "VALIDATION_ERROR")
    assert container.index.snapshot is before


@pytest.mark.parametrize(
    "body",
    [
        {"documents": []},
        {"documents": [doc(doc_id=f"match-2026-mw06-{i}-1") for i in range(101)]},
        {"documents": [NEW_MATCH], "extra": 1},
        {},
    ],
)
async def test_invalid_upsert_bodies_are_422(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    assert_problem(await client.post("/index/upsert", json=body), 422, "VALIDATION_ERROR")


async def test_delete_removes_the_document_from_search(client: httpx.AsyncClient) -> None:
    await upsert(client, NEW_MATCH)
    response = await client.delete(f"/index/{NEW_MATCH['doc_id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert NEW_MATCH["doc_id"] not in await doc_ids_found(client, "Liverpool Manchester City")


async def test_deleting_again_is_false(client: httpx.AsyncClient) -> None:
    await upsert(client, NEW_MATCH)
    await client.delete(f"/index/{NEW_MATCH['doc_id']}")
    before = (await client.get("/index/stats")).json()["index_version"]
    response = await client.delete(f"/index/{NEW_MATCH['doc_id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": False}
    assert (await client.get("/index/stats")).json()["index_version"] == before


async def test_stats_match_the_store_and_the_snapshot(
    client: httpx.AsyncClient, container: Container
) -> None:
    await upsert(client, NEW_MATCH)
    response = await client.get("/index/stats")
    assert response.status_code == 200
    body = response.json()
    stored = container.store.load_all()
    snapshot = container.index.snapshot
    assert snapshot is not None
    assert body == {
        "documents": 7,
        "chunks": SAMPLE_CHUNK_COUNT + 1,
        "by_category": {"trivia": 3, "match_report": 2, "standings": 1, "fixtures": 1},
        "index_version": snapshot.index_version,
    }
    assert body["chunks"] == len(stored) == snapshot.faiss_count == snapshot.bm25_count
    assert body["documents"] == len({s.chunk.doc_id for s in stored})


async def test_stats_before_the_index_loads_are_503(unloaded_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=unloaded_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        assert_problem(await c.get("/index/stats"), 503, "INDEX_NOT_READY")
