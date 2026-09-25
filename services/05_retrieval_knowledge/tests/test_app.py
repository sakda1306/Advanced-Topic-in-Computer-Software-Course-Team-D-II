"""/health, Problem-JSON, request id and body limits (CONTRACT §0)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from tests.conftest import assert_problem, make_settings


async def test_health_matches_contract(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "retrieval", "version": "0.1.0"}
    assert response.headers["x-request-id"] == "abc-123"


async def test_unsafe_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "bad id with spaces"})
    assert len(response.headers["x-request-id"]) == 36


async def test_unknown_path_is_problem_json(client: httpx.AsyncClient) -> None:
    assert_problem(await client.get("/nope"), 404, "NOT_FOUND")


async def test_search_body_over_64kb_is_413(client: httpx.AsyncClient) -> None:
    response = await client.post("/search", json={"query": "x" * 70_000})
    assert_problem(response, 413, "PAYLOAD_TOO_LARGE")


async def test_upsert_path_allows_larger_bodies(client: httpx.AsyncClient) -> None:
    # The route arrives in PR ②; the limit for it is already 5 MB, so this is not a 413.
    response = await client.post("/index/upsert", json={"documents": [{"text": "x" * 70_000}]})
    assert response.status_code == 404


async def test_non_json_body_is_415(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/search", content=b"query=x", headers={"content-type": "text/plain"}
    )
    assert_problem(response, 415, "UNSUPPORTED_MEDIA_TYPE")


def test_settings_in_tests_ignore_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_SHA", "from-env")
    monkeypatch.setenv("CANDIDATE_K", "1")
    settings = make_settings(tmp_path)
    assert settings.version == "0.1.0"
    assert settings.candidate_k == 20
