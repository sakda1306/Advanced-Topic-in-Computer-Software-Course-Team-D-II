import json
import unittest
from pathlib import Path

from app.decisions import classify_intent, decide
from app.teams import TeamDirectory


CASES = Path(__file__).with_name("routing_cases.jsonl")
TEAMS = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
CONTEXT = {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}


class DecisionTests(unittest.TestCase):
    def test_forty_routing_cases(self):
        cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 40)
        self.assertEqual({route: sum(case["route"] == route for case in cases)
                          for route in {case["route"] for case in cases}},
                         {"football_rag": 8, "general_ai": 8, "local_ai": 8,
                          "clarify": 8, "decline": 8})
        for case in cases:
            with self.subTest(query=case["query"]):
                result = decide(case["query"], CONTEXT, [], TEAMS)
                self.assertIsNotNone(result)
                self.assertEqual(result.route, case["route"])
                if "intent" in case:
                    self.assertEqual(result.intent, case["intent"])

    def test_classifier_threshold_and_mapping(self):
        self.assertEqual(classify_intent("match_result", 0.75).route, "football_rag")
        self.assertIsNone(classify_intent("fixture_schedule", 0.74))
        self.assertEqual(classify_intent("prediction", 0.9).route, "local_ai")
        self.assertIsNone(classify_intent("unknown", 0.99))

    def test_yesterday_date_filter(self):
        result = decide("เมื่อวานปืนใหญ่ชนะไหม", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters["category"], ["match_report"])
        self.assertEqual(result.filters["team_ids"], [57])
        self.assertEqual(result.filters["date_from"], "2026-09-25")
        self.assertEqual(result.filters["date_to"], "2026-09-25")
        self.assertNotIn("matchweek", result.filters)
        self.assertIn("Arsenal", result.rewritten_query)
        self.assertIn("เมื่อวานปืนใหญ่ชนะไหม", result.rewritten_query)

    def test_rewrite_keeps_person_and_question_condition(self):
        query = "ใครยิงประตูชัยให้ลิเวอร์พูลในนัดชิงปี 2005"
        result = decide(query, CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "trivia_history")
        self.assertIn(query, result.rewritten_query)

    def test_followup_reuses_recent_team(self):
        history = [{"role": "user", "content": "อาร์เซนอลนัดล่าสุดชนะไหม"},
                   {"role": "assistant", "content": "อาร์เซนอลชนะ"}]
        result = decide("แล้วนัดก่อนหน้าล่ะ", CONTEXT, history, TEAMS)
        self.assertEqual(result.route, "football_rag")
        self.assertEqual(result.filters["team_ids"], [57])
        self.assertIn("Arsenal", result.rewritten_query)

    def test_ambiguous_united(self):
        self.assertEqual(decide("ยูไนเต็ดนัดล่าสุดชนะไหม", CONTEXT, [], TEAMS).route, "clarify")

    def test_alias_does_not_match_inside_english_word(self):
        self.assertEqual(TEAMS.find("Arsenalization"), [])

    def test_prediction_teams_follow_question_order(self):
        result = decide("ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [65, 64])

    def test_live_team_refresh_keeps_offline_aliases(self):
        live = TeamDirectory.from_payload({"teams": [{"team_id": 57, "name": "Arsenal FC",
            "short_name": "Arsenal", "aliases": ["ใหม่"]}]})
        merged = TEAMS.merged(live)
        self.assertEqual(merged.find("ปืนใหญ่")[0].team_id, 57)
        self.assertEqual(merged.find("ใหม่")[0].team_id, 57)


if __name__ == "__main__":
    unittest.main()
