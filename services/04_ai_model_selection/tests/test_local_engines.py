from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_local_classify_returns_expected_shape():
    r = client.post("/local/classify", json={"request_id": "c1", "text": "ปืนใหญ่ชนะกี่ลูกเมื่อคืน"})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "local_ai"
    assert body["data"]["label"] in {
        "trivia_history",
        "match_result",
        "fixture_schedule",
        "standings_stats",
        "weekly_summary",
        "general_football",
        "prediction",
        "out_of_scope",
    }
    assert 0 <= body["data"]["score"] <= 1
    assert len(body["data"]["top_k"]) == 3
    assert body["token_usage"] == {"input": 0, "output": 0}
    assert body["model"] == "tfidf-logreg-v1"
    assert body["content"].startswith("intent: ")


def test_local_classify_high_confidence_match_result():
    r = client.post(
        "/local/classify", json={"request_id": "c2", "text": "เมื่อวานลิเวอร์พูลเจอใคร ผลเท่าไหร่"}
    )
    body = r.json()
    assert body["data"]["label"] == "match_result"


def test_local_classify_model_unavailable_returns_503():
    from app.local_classifier import ModelNotLoadedError

    with patch("app.main.classify_intent", side_effect=ModelNotLoadedError("no model file")):
        r = client.post("/local/classify", json={"request_id": "c3", "text": "test"})
    assert r.status_code == 503
    assert r.json()["code"] == "MODEL_UNAVAILABLE"


def test_local_predict_returns_501_not_implemented():
    r = client.post(
        "/local/predict",
        json={"request_id": "p1", "home_team_id": 57, "away_team_id": 61, "season": "2026"},
    )
    assert r.status_code == 501
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "NOT_IMPLEMENTED"
    assert body["request_id"] == "p1"
