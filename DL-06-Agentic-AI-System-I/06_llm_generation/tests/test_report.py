def _base_match(**overrides):
    m = {
        "match_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "season": "2026",
        "matchweek": 5,
        "kickoff": "2026-09-20T18:30:00+07:00",
        "status": "FINISHED",
        "home": {"team_id": 57, "name": "Arsenal"},
        "away": {"team_id": 61, "name": "Chelsea"},
        "score": {"home": 2, "away": 1, "half_time": {"home": 1, "away": 0}},
        "events": [],
        "detail_source": "none",
    }
    m.update(overrides)
    return m


def test_weekly_report_full(client):
    body = {
        "request_id": "55555555-5555-5555-5555-555555555555",
        "season": "2026",
        "matchweek": 5,
        "language": "th",
        "matches": [_base_match()],
        "standings": [
            {
                "position": 1, "team_id": 57, "name": "Arsenal", "played": 5, "won": 4,
                "draw": 1, "lost": 0, "goals_for": 12, "goals_against": 4,
                "goal_difference": 8, "points": 13, "form": "WWDWW",
            }
        ],
        "top_scorers": [{"player": "E. Haaland", "team_id": 65, "goals": 7, "assists": 1}],
    }
    resp = client.post("/report/weekly", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "2026/27" in data["title"]
    assert "## ผลการแข่งขัน" in data["markdown"]
    assert "## ตารางคะแนน" in data["markdown"]
    assert "## ดาวซัลโว" in data["markdown"]
    assert "2-1" in data["markdown"]


def test_weekly_report_postponed_no_score(client):
    body = {
        "season": "2026",
        "matchweek": 6,
        "language": "th",
        "matches": [_base_match(status="POSTPONED", score=None)],
        "standings": [],
        "top_scorers": [],
    }
    resp = client.post("/report/weekly", json=body)
    data = resp.json()
    assert "เลื่อนการแข่งขัน" in data["markdown"]
    assert "## ตารางคะแนน" not in data["markdown"]


def test_weekly_report_empty_matches_422(client):
    resp = client.post(
        "/report/weekly",
        json={"season": "2026", "matchweek": 6, "language": "th", "matches": []},
    )
    assert resp.status_code == 422


def test_weekly_report_pipe_in_team_name_safe(client):
    body = {
        "season": "2026",
        "matchweek": 7,
        "language": "th",
        "matches": [_base_match(home={"team_id": 1, "name": "Team | Pipe"})],
        "standings": [
            {
                "position": 1, "team_id": 1, "name": "Team | Pipe", "played": 1, "won": 1,
                "draw": 0, "lost": 0, "goals_for": 2, "goals_against": 1,
                "goal_difference": 1, "points": 3, "form": "W",
            }
        ],
        "top_scorers": [],
    }
    resp = client.post("/report/weekly", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "Team \\| Pipe" in data["markdown"]
