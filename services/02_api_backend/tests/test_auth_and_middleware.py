"""/health, login / logout / me / preferences, middleware (CONTRACT §0, §1)."""

from __future__ import annotations

import httpx

from tests.conftest import DEMO_PASSWORD, assert_problem


async def test_health_matches_contract(client: httpx.AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api", "version": "0.1.0"}
    assert response.headers["x-request-id"] == "abc-123"


async def test_request_id_is_created_when_missing(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert len(response.headers["x-request-id"]) == 36


async def test_login_sets_httponly_cookie(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login", json={"username": "demo1", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["username"] == "demo1"
    assert user["role"] == "user"
    assert user["language"] == "th"
    assert set(user) == {"id", "username", "display_name", "role", "favorite_team_id", "language"}
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("access_token=")
    assert "HttpOnly" in cookie

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "demo1"


async def test_login_wrong_password(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"username": "demo1", "password": "nope"})
    assert_problem(response, 401, "UNAUTHENTICATED")


async def test_login_unknown_user(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert_problem(response, 401, "UNAUTHENTICATED")


async def test_me_without_cookie(client: httpx.AsyncClient) -> None:
    assert_problem(await client.get("/api/auth/me"), 401, "UNAUTHENTICATED")


async def test_bad_token(client: httpx.AsyncClient) -> None:
    client.cookies.set("access_token", "not-a-jwt")
    assert_problem(await client.get("/api/auth/me"), 401, "UNAUTHENTICATED")


async def test_logout_clears_cookie(demo: httpx.AsyncClient) -> None:
    response = await demo.post("/api/auth/logout")
    assert response.json() == {"ok": True}
    assert_problem(await demo.get("/api/auth/me"), 401, "UNAUTHENTICATED")


async def test_preferences(demo: httpx.AsyncClient) -> None:
    response = await demo.patch(
        "/api/me/preferences", json={"favorite_team_id": 57, "language": "en"}
    )
    assert response.status_code == 200
    user = response.json()["user"]
    assert user["favorite_team_id"] == 57
    assert user["language"] == "en"

    # Only the fields sent are changed; null clears the team.
    response = await demo.patch("/api/me/preferences", json={"favorite_team_id": None})
    user = response.json()["user"]
    assert user["favorite_team_id"] is None
    assert user["language"] == "en"


async def test_preferences_rejects_bad_language(demo: httpx.AsyncClient) -> None:
    response = await demo.patch("/api/me/preferences", json={"language": "jp"})
    assert_problem(response, 422, "VALIDATION_ERROR")


async def test_non_json_body_is_415(demo: httpx.AsyncClient) -> None:
    response = await demo.post(
        "/api/chat", content=b"hello", headers={"content-type": "text/plain"}
    )
    assert_problem(response, 415, "UNSUPPORTED_MEDIA_TYPE")


async def test_oversized_body_is_413(demo: httpx.AsyncClient) -> None:
    response = await demo.post("/api/chat", json={"message": "x" * 70_000})
    assert_problem(response, 413, "PAYLOAD_TOO_LARGE")


async def test_unknown_path_is_problem_json(client: httpx.AsyncClient) -> None:
    assert_problem(await client.get("/api/nope"), 404, "NOT_FOUND")


async def test_security_headers(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
