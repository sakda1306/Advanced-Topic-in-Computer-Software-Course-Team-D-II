"""Test settings that ignore the machine's env, an app client, Problem-JSON checks."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from app.core.config import Settings
from app.main import create_app

TEST_DATA = Path(__file__).parent / "data"


class IsolatedSettings(Settings):
    """Only the values given here and the defaults: no env vars, no `.env` file."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        *_sources: PydanticBaseSettingsSource,
        **_kwargs: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "kb_db_path": str(tmp_path / "kb.sqlite"),
        "aliases_file": str(TEST_DATA / "team_aliases.json"),
        "log_level": "WARNING",
        "log_json": False,
    }
    values.update(overrides)
    return IsolatedSettings(**values)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def assert_problem(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = response.json()
    assert body["code"] == code
    assert body["status"] == status
    assert body["service"] == "retrieval"
    assert body["request_id"] == response.headers["x-request-id"]
    return body
