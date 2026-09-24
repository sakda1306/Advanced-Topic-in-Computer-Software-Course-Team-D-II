"""/api/football/* pass-through to 07 (CONTRACT §1, §7)."""

from __future__ import annotations

import httpx
import pytest

from tests.conftest import DownTransport, assert_problem


async def test_standings(demo: httpx.AsyncClient) -> None:
    body = (await demo.get("/api/football/standings?season=2026")).json()
    assert body["season"] == "2026"
    assert body["rows"][0]["team_id"] == 57


async def test_fixtures_filters_are_forwarded(demo: httpx.AsyncClient) -> None:
    body = (await demo.get("/api/football/fixtures?team_id=64&status=SCHEDULED")).json()
    assert [m["home"]["name"] for m in body["matches"]] == ["Liverpool"]


async def test_match_and_missing_match(demo: httpx.AsyncClient) -> None:
    match_id = "7d3c1b52-6a8f-4d8e-9c1a-5e2f0b1a9c01"
    assert (await demo.get(f"/api/football/matches/{match_id}")).json()["score"]["home"] == 2
    assert_problem(await demo.get("/api/football/matches/unknown"), 404, "NOT_FOUND")


async def test_weekly_report_only_published(
    demo: httpx.AsyncClient, admin: httpx.AsyncClient
) -> None:
    # The stub starts with a draft only.
    assert_problem(await demo.get("/api/football/reports/weekly"), 404, "NOT_FOUND")
    await admin.post("/api/admin/reports/2026/5/publish")
    body = (await demo.get("/api/football/reports/weekly")).json()
    assert body["status"] == "published"
    await admin.post("/api/admin/reports/2026/5/unpublish")


async def test_status_shape(demo: httpx.AsyncClient) -> None:
    body = (await demo.get("/api/football/status")).json()
    assert set(body) == {"current_season", "current_matchweek", "last_ingest_at", "quota"}


async def test_season_is_validated(demo: httpx.AsyncClient) -> None:
    assert_problem(await demo.get("/api/football/standings?season=26"), 422, "VALIDATION_ERROR")


async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert_problem(await client.get("/api/football/standings"), 401, "UNAUTHENTICATED")


@pytest.mark.parametrize("football_transport", [DownTransport()])
async def test_football_data_down_is_502(demo: httpx.AsyncClient) -> None:
    response = await demo.get("/api/football/standings")
    assert_problem(response, 502, "FOOTBALL_DATA_UNAVAILABLE")


@pytest.mark.parametrize(
    "football_transport",
    [
        httpx.MockTransport(
            lambda r: httpx.Response(409, json={"code": "JOB_ALREADY_RUNNING", "status": 409})
        )
    ],
)
async def test_07_conflict_codes_pass_through(admin: httpx.AsyncClient) -> None:
    response = await admin.post("/api/admin/pipeline/ingest", json={"scope": "all"})
    assert_problem(response, 409, "JOB_ALREADY_RUNNING")
    # Nothing happened, so nothing is audited.
    assert (await admin.get("/api/admin/audit")).json()["items"] == []
