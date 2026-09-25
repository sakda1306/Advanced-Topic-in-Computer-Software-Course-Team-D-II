from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "engines"


def test_general_success_primary():
    with patch("app.main.call_general_ai") as mock_call:
        mock_call.return_value = ("กฎล้ำหน้าคือ...", "openai/gpt-oss-120b", {"input": 40, "output": 55})
        r = client.post(
            "/general",
            json={"request_id": "req-1", "query": "กฎล้ำหน้าคืออะไร", "history": [], "language": "th"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "general_ai"
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["sources"] == []
    assert body["data"] is None
    assert body["token_usage"] == {"input": 40, "output": 55}
    assert "latency_ms" in body


def test_general_uses_history_and_language():
    with patch("app.main.call_general_ai") as mock_call:
        mock_call.return_value = ("Offside is...", "gemini-2.0-flash", {"input": 30, "output": 40})
        r = client.post(
            "/general",
            json={
                "request_id": "req-2",
                "query": "Explain it in more detail",
                "history": [
                    {"role": "user", "content": "What is offside?"},
                    {"role": "assistant", "content": "It's a rule about..."},
                ],
                "language": "en",
            },
        )
    assert r.status_code == 200
    call_kwargs = mock_call.call_args.kwargs
    messages = call_kwargs["messages"]
    # system + 2 history + 1 user = 4
    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert "English" in messages[0]["content"]
    assert messages[-1]["content"] == "Explain it in more detail"


def test_general_both_providers_down_returns_503_problem_json():
    from app.llm_client import LLMUnavailableError

    with patch("app.main.call_general_ai", side_effect=LLMUnavailableError("groq down | gemini down")):
        r = client.post(
            "/general",
            json={"request_id": "req-3", "query": "อธิบายกติกาจุดโทษ", "history": [], "language": "th"},
        )
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "LLM_UNAVAILABLE"
    assert body["service"] == "engines"
    assert body["request_id"] == "req-3"


def test_general_missing_query_returns_422():
    r = client.post("/general", json={"request_id": "req-4", "language": "th"})
    assert r.status_code == 422
