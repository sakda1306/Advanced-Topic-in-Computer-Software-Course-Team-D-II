import json
import unittest
from pathlib import Path

from app.decisions import classify_intent, decide
from app.teams import TeamDirectory


CASES = Path(__file__).with_name("routing_cases.jsonl")
TEAMS = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
CONTEXT = {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}


class DecisionTests(unittest.TestCase):
    def test_routing_cases(self):
        cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 41)
        self.assertEqual({route: sum(case["route"] == route for case in cases)
                          for route in {case["route"] for case in cases}},
                         {"football_rag": 9, "general_ai": 8, "local_ai": 8,
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

    def test_vague_followup_uses_latest_classifiable_user_intent(self):
        history = [{"role": "user", "content": "ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล"},
                   {"role": "assistant", "content": "ยังไม่พร้อม"},
                   {"role": "user", "content": "อาร์เซนอลอยู่อันดับเท่าไร"}]
        result = decide("แล้วล่ะ", CONTEXT, history, TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.route, "football_rag")

    def test_match_discipline_questions_remain_factual(self):
        for query in ("เมื่อวานลิเวอร์พูลได้ลูกโทษไหม", "ใครโดนใบแดงนัดล่าสุด"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "match_result")
                self.assertEqual(result.filters["category"], ["match_report"])

    def test_discipline_rule_question_stays_general(self):
        result = decide("กฎใบแดงคืออะไร", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "general_football")

    def test_title_history_when_is_trivia(self):
        result = decide("ลิเวอร์พูลได้แชมป์ครั้งล่าสุดเมื่อไร", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "trivia_history")
        self.assertEqual(result.filters["category"], ["trivia"])
        self.assertNotIn("season", result.filters)

    def test_team_trivia_does_not_filter_unlabeled_trivia_documents(self):
        result = decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [57])
        self.assertEqual(result.filters, {"category": ["trivia"]})

    def test_full_manchester_club_names_are_recognized(self):
        for name, team_id in (("Manchester United", 66), ("Manchester City", 65)):
            with self.subTest(name=name):
                result = decide(f"{name} นัดล่าสุดชนะไหม", CONTEXT, [], TEAMS)
                self.assertEqual(result.team_ids, [team_id])
                self.assertEqual(result.intent, "match_result")

    def test_other_city_club_is_not_man_city(self):
        result = decide("เลสเตอร์ ซิตี้ ได้แชมป์ปีไหน", CONTEXT, [], TEAMS)
        self.assertNotIn(65, result.team_ids if result else [])

    def test_out_of_range_matchweek_is_clarified(self):
        for query in ("นัดที่ 45 ผลแข่งปืนใหญ่", "matchweek 0 Arsenal result"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.route, "clarify")

    def test_english_top_scorer_uses_standings(self):
        result = decide("who is the top scorer", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.filters["category"], ["standings"])

    def test_weekly_summary_uses_spaced_matchweek(self):
        result = decide("สรุปพรีเมียร์ลีกนัดที่ 3", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "weekly_summary")
        self.assertEqual(result.filters["matchweek"], 3)

    def test_current_scorer_filters_current_matchweek(self):
        result = decide("ใครนำดาวซัลโวตอนนี้", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters["matchweek"], 5)

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
