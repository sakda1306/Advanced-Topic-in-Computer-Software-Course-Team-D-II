"""FakeLLM + dependency override — pytest ต้องผ่านโดยไม่มี key ไม่ต่อเน็ต"""
from __future__ import annotations

import os

os.environ.setdefault("LLM_MOCK", "true")

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

settings.llm_mock = True


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
