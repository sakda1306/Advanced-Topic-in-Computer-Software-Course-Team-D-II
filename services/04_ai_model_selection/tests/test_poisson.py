import pytest

from app.poisson import TeamStrength, match_outcome_probabilities


def test_probabilities_sum_to_one():
    home = TeamStrength(attack_goals_per_match=2.1, defense_goals_conceded_per_match=0.9, matches_used=10)
    away = TeamStrength(attack_goals_per_match=1.3, defense_goals_conceded_per_match=1.4, matches_used=10)
    result = match_outcome_probabilities(home, away)
    total = result["home_win"] + result["draw"] + result["away_win"]
    assert total == pytest.approx(1.0, abs=1e-3)


def test_stronger_home_team_favored():
    strong = TeamStrength(attack_goals_per_match=2.5, defense_goals_conceded_per_match=0.7, matches_used=10)
    weak = TeamStrength(attack_goals_per_match=0.8, defense_goals_conceded_per_match=2.0, matches_used=10)
    result = match_outcome_probabilities(strong, weak)
    assert result["home_win"] > result["away_win"]
    assert result["home_win"] > result["draw"]


def test_evenly_matched_teams_have_similar_outcome_split():
    a = TeamStrength(attack_goals_per_match=1.4, defense_goals_conceded_per_match=1.2, matches_used=10)
    b = TeamStrength(attack_goals_per_match=1.4, defense_goals_conceded_per_match=1.2, matches_used=10)
    result = match_outcome_probabilities(a, b)
    # เจ้าบ้านยังได้เปรียบจาก home advantage แต่ไม่ควรต่างกันสุดโต่ง
    assert result["home_win"] > result["away_win"]
    assert result["away_win"] > 0.15


def test_expected_goals_never_zero_or_negative():
    from app.poisson import expected_goals

    tiny = TeamStrength(attack_goals_per_match=0.0, defense_goals_conceded_per_match=0.0, matches_used=1)
    xg = expected_goals(tiny, tiny, is_home=True)
    assert xg > 0
