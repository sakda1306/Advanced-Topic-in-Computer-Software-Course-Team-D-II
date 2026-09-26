"""Run the 40 routing cases through the complete router with deterministic service replies."""

import asyncio
import json
from pathlib import Path

from app.router import Router
from app.teams import TeamDirectory


ROOT = Path(__file__).resolve().parent


class EvalClients:
    async def search(self, payload, request_id):
        return {"chunks": [{"text": "Fixture and standings sample",
                            "source": {"doc_id": "eval-1", "title": "Sample",
                                       "category": payload["filters"]["category"][0],
                                       "origin": "fixture", "ref": 1}}]}

    async def general(self, payload, request_id):
        return {"content": "Sample explanation"}

    async def predict(self, payload, request_id):
        return {"content": "Sample prediction"}

    async def generate(self, payload, request_id):
        return {"answer": "Sample answer", "sources": [item["source"] for item in payload["contexts"]]}

    async def classify(self, payload, request_id):
        raise AssertionError("All benchmark questions must use a deterministic rule or guard")

    async def llm_decide(self, query, request_id):
        raise AssertionError("All benchmark questions must use a deterministic rule or guard")


async def evaluate():
    cases = [json.loads(line) for line in (ROOT / "tests" / "routing_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(cases) != 40:
        raise ValueError("Expected 40 routing cases")
    teams = TeamDirectory.from_file(ROOT / "data" / "team_aliases.json")
    router = Router(EvalClients(), teams)
    failures = []
    for index, case in enumerate(cases, 1):
        actual = await router.route({"request_id": f"eval-{index}", "query": case["query"],
                                     "history": [], "user": {"language": "th"},
                                     "context": {"season": "2026", "current_matchweek": 5,
                                                 "now": "2026-09-26T10:00:00+07:00"}})
        if actual["route"] != case["route"] or ("intent" in case and actual["trace"]["intent"] != case["intent"]):
            failures.append({"query": case["query"], "expected_route": case["route"],
                             "actual_route": actual["route"], "expected_intent": case.get("intent"),
                             "actual_intent": actual["trace"]["intent"]})
    correct = len(cases) - len(failures)
    return {"total": len(cases), "correct": correct, "route_accuracy": round(correct / len(cases), 4),
            "failures": failures, "service_mode": "deterministic_fixtures"}


if __name__ == "__main__":
    report = asyncio.run(evaluate())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not report["failures"] else 1)
