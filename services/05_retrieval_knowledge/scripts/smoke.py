"""Smoke test against a running retrieval service with the real model and trivia file.

    RETRIEVAL_URL=http://localhost:8000 python scripts/smoke.py

Waits for /ready, then checks the CONTRACT §4 shape on the real knowledge base.
Exits 1 on the first failed check.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx

URL = os.environ.get("RETRIEVAL_URL", "http://localhost:8000")
FIRST_QUESTION = (
    "It is alleged that this country 'sold out' to Argentina in a 1978 World Cup Group 2 game."
)


def check(name: str, ok: bool, response: httpx.Response | None = None) -> None:
    if not ok:
        detail = f" -> {response.status_code} {response.text[:300]}" if response else ""
        print(f"FAIL {name}{detail}")
        sys.exit(1)
    print(f"ok   {name}")


def wait_ready(client: httpx.Client, seconds: int = 180) -> httpx.Response:
    deadline = time.monotonic() + seconds
    while True:
        try:
            response = client.get("/ready")
            if response.status_code == 200 or time.monotonic() > deadline:
                return response
        except httpx.TransportError:
            if time.monotonic() > deadline:
                raise
        time.sleep(2)


def search(client: httpx.Client, **body: Any) -> httpx.Response:
    return client.post("/search", json=body)


def main() -> None:
    client = httpx.Client(base_url=URL, timeout=30)
    # Waited for first: the port opens only after the embedding model has loaded.
    response = wait_ready(client)
    check("GET /ready", response.status_code == 200 and response.json()["chunks"] > 1900, response)
    response = client.get("/health")
    check("GET /health", response.json().get("service") == "retrieval", response)

    for mode in ("hybrid", "bm25", "vector"):
        response = search(client, query=FIRST_QUESTION, mode=mode)
        chunks = response.json().get("chunks", [])
        check(
            f"{mode}: the question finds trivia-0001 first",
            response.status_code == 200 and chunks[0]["source"]["doc_id"] == "trivia-0001",
            response,
        )

    response = search(client, query="Who won", filters={"category": ["match_report"]})
    check("no live documents yet -> 200 and []", response.json().get("chunks") == [], response)
    response = search(client, query="Arsenal", top_k=0)
    check(
        "top_k 0 -> 422 Problem-JSON",
        response.status_code == 422 and response.json().get("service") == "retrieval",
        response,
    )
    print("smoke passed")


if __name__ == "__main__":
    main()
