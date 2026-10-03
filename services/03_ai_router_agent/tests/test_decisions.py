import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.decisions import (INTENT_MAP, classify_intent, decide, from_intent, historical_scorer_season,
                           history_filters, prediction_kind)
from app.teams import TeamDirectory


CASES = Path(__file__).with_name("routing_cases.jsonl")
CHAT_CASES = Path(__file__).with_name("chat_cases.jsonl")
TEAMS = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
CONTEXT = {"season": "2026", "current_matchweek": 5, "now": "2026-09-26T10:00:00+07:00"}


class DecisionTests(unittest.TestCase):
    def test_season_questions_are_prediction_intent(self):
        for query in ("ใครจะได้แชมป์พรีเมียร์ลีกปีนี้", "อาร์เซนอลมีโอกาสติดท็อป 4 กี่เปอร์เซ็นต์",
                      "ใครเสี่ยงตกชั้นมากที่สุด", "ทีมไหนจะตกชั้น", "Who will be relegated this season?",
                      "What are Arsenal's chances of winning the title?"):
            with self.subTest(query=query):
                self.assertEqual(decide(query, CONTEXT, [], TEAMS).intent, "prediction")

    def test_history_questions_stay_trivia(self):
        for query in ("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง", "ลิเวอร์พูลได้แชมป์ครั้งล่าสุดเมื่อไร",
                      "เชลซีเคยได้แชมป์พรีเมียร์ลีกกี่ครั้ง"):
            with self.subTest(query=query):
                self.assertEqual(decide(query, CONTEXT, [], TEAMS).intent, "trivia_history")

    def test_prediction_kind(self):
        cases = (
            ("ลิเวอร์พูลกับซิตี้ใครจะชนะ", [64, 65], "match"),
            ("อาร์เซนอลกับลิเวอร์พูล ใครจะได้แชมป์", [57, 64], "season"),
            ("Arsenal, City or Liverpool, who will win the title?", [57, 65, 64], "season"),
            ("ใครจะได้แชมป์ปีนี้", [], "season"),
            ("อาร์เซนอลมีโอกาสติดท็อป 4 กี่ %", [57], "season"),
            ("ใครเสี่ยงตกชั้น", [], "season"),
            ("อาร์เซนอลมีโอกาสชนะไหม", [57], "needs_team"),
            ("ทำนายผลหน่อย", [], "needs_team"),
        )
        for query, team_ids, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(prediction_kind(query, team_ids), expected)

    def test_historical_scorer_year_forms(self):
        cases = (
            ("ลีคปี 2025 ใครยิงเยอะสุด", ("2025", True)),
            ("พรีเมียร์ลีกฤดูกาล 2025/26 ดาวซัลโว", ("2025", False)),
            ("2025-2026 Premier League top scorer", ("2025", False)),
            ("พรีเมียร์ลีก 25/26 ใครทำประตูมากที่สุด", ("2025", False)),
            ("ใครยิงเยอะสุดตอนนี้", None),
            ("ใครยิงประตูมากที่สุดตลอดกาลปี 2025", None),
            ("Who was the top scorer last season", ("2025", False)),
            ("ใครเป็นดาวซัลโวซีซั่นที่แล้ว", ("2025", False)),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(historical_scorer_season(query, "2026"), expected)

    def test_explicit_current_season_scorer_uses_live_standings(self):
        result = decide("พรีเมียร์ลีกฤดูกาล 2026/27 ดาวซัลโว", CONTEXT, [], TEAMS)
        self.assertEqual(result.intent, "standings_stats")
        self.assertEqual(result.filters["season"], "2026")
        self.assertIn("top scorer", result.rewritten_query)

    def test_scorer_review_edge_cases(self):
        cases = (
            ("ดาวซัลโว Everton ตอนนี้", "standings_stats"),
            ("ดาวซัลโวฤดูกาล 2026", "standings_stats"),
            ("ดาวซัลโวฤดูกาล 2026/2027", "standings_stats"),
            ("ดาวซัลโวซีซั่น 2025/26", "trivia_history"),
            ("ผู้รักษาประตูคนไหนเซฟมากที่สุด", "player_info"),
            ("ทีมไหนเสียประตูมากที่สุด", None),
            ("Who was the top scorer last season", "trivia_history"),
            ("ใครเป็นดาวซัลโวซีซั่นที่แล้ว", "trivia_history"),
            ("ดาวซัลโวปีที่แล้ว", "trivia_history"),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                decision = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(decision.intent if decision else None, expected)

    def test_routing_cases(self):
        cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(cases), 44)
        self.assertEqual({route: sum(case["route"] == route for case in cases)
                          for route in {case["route"] for case in cases}},
                         {"football_rag": 9, "general_ai": 8, "local_ai": 11,
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
        self.assertEqual(result.filters["category"], ["trivia", "historical"])
        self.assertNotIn("season", result.filters)

    def test_team_trivia_does_not_filter_unlabeled_trivia_documents(self):
        result = decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [57])
        self.assertEqual(result.filters, {"category": ["trivia", "historical"]})

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

    def test_current_top_scorer_phrases_use_standings(self):
        for query in (
            "ใครยิงเยอะสุดในลีกตอนนี้",
            "ครยิงเยอะสุดในลีกตอนนี้",
            "ใครทำประตูมากที่สุดในพรีเมียร์ลีกฤดูกาลนี้",
            "ใครทำประตูเยอะที่สุด",
            "ใครยิงเยอะที่สุดตอนนี้",
            "นักเตะคนไหนยิงประตูมากที่สุดฤดูกาลนี้",
            "Who has the most goals this season",
        ):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "standings_stats")
                self.assertEqual(result.filters["category"], ["standings"])
                self.assertEqual(result.filters["matchweek"], 5)
                if query != "Who has the most goals this season":
                    self.assertIn("top scorer", result.rewritten_query)

    def test_historical_scorer_does_not_use_current_standings(self):
        for query in ("ใครยิงมากที่สุดในลีกปี 2020", "ใครยิงประตูมากที่สุดตลอดกาลของพรีเมียร์ลีก"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "trivia_history")

    def test_ambiguous_united(self):
        self.assertEqual(decide("ยูไนเต็ดนัดล่าสุดชนะไหม", CONTEXT, [], TEAMS).route, "clarify")

    def test_alias_does_not_match_inside_english_word(self):
        self.assertEqual(TEAMS.find("Arsenalization"), [])

    def test_prediction_teams_follow_question_order(self):
        result = decide("ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [65, 64])

    def test_liverpool_duck_alias_resolves_offline(self):
        self.assertEqual(TEAMS.find("เป็ดแดงเตะวันไหน")[0].team_id, 64)
        self.assertIn("Liverpool", TEAMS.replace_aliases("เป็ดแดงเตะวันไหน"))

    def test_live_team_refresh_keeps_offline_aliases(self):
        live = TeamDirectory.from_payload({"teams": [{"team_id": 57, "name": "Arsenal FC",
            "short_name": "Arsenal", "aliases": ["ใหม่"]}]})
        merged = TEAMS.merged(live)
        self.assertEqual(merged.find("ปืนใหญ่")[0].team_id, 57)
        self.assertEqual(merged.find("ใหม่")[0].team_id, 57)


class PlayerInfoTests(unittest.TestCase):
    """CONTRACT v1.5: the classifier (04) does not know player_info, so rules must catch it."""

    PLAYER_QUERIES = [
        ("อาร์เซนอลมีนักเตะใครบ้าง", [57]),
        ("ขอดูสควอดของเชลซีหน่อย", [61]),
        ("โค้ชของลิเวอร์พูลคือใคร", [64]),
        ("ผู้จัดการทีมแมนซิตี้คนปัจจุบันคือใคร", [65]),
        ("ซาก้าเล่นตำแหน่งอะไร", []),
        ("ฮาลันด์อายุเท่าไหร่", []),
        ("นักเตะสัญชาติไทยในพรีเมียร์ลีกมีใครบ้าง", []),
        ("ผู้รักษาประตูของนิวคาสเซิลมีใครบ้าง", [67]),
        ("Which players are in the Chelsea squad", [61]),
        ("What position does Salah play", []),
        ("Who is the manager of Arsenal", [57]),
        ("How old is Erling Haaland", []),
    ]

    def test_player_questions_route_to_player_documents(self):
        for query, team_ids in self.PLAYER_QUERIES:
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertIsNotNone(result)
                self.assertEqual(result.intent, "player_info")
                self.assertEqual(result.route, "football_rag")
                self.assertEqual(result.layer, "rules")
                self.assertEqual(result.filters["category"], ["player"])
                self.assertEqual(result.filters.get("team_ids", []), team_ids)
                self.assertNotIn("matchweek", result.filters)

    def test_player_rewrite_is_english_and_keeps_the_question(self):
        query = "อาร์เซนอลมีนักเตะใครบ้าง"
        result = decide(query, CONTEXT, [], TEAMS)
        self.assertIn("Arsenal", result.rewritten_query)
        self.assertIn("squad", result.rewritten_query)
        self.assertIn(query, result.rewritten_query)

    def test_neighbouring_questions_keep_their_intent(self):
        cases = [
            ("ใครนำดาวซัลโวตอนนี้", "standings_stats"),
            ("ดาวซัลโวของอาร์เซนอลคือใคร", "standings_stats"),
            ("อาร์เซนอลอยู่ตำแหน่งไหนในตารางคะแนน", "standings_stats"),
            ("ผู้รักษาประตูใช้มือได้ตอนไหน", "general_football"),
            ("ผู้เล่นคนไหนโดนใบแดงเมื่อวาน", "match_result"),
            ("โค้ชคนไหนพาทีมได้แชมป์พรีเมียร์ลีกมากที่สุด", "trivia_history"),
            ("นักเตะคนไหนยิงประตูมากที่สุดฤดูกาลนี้", "standings_stats"),
            # This question still falls through to the classifier/LLM.
            ("What position is Arsenal in the table", None),
        ]
        for query, intent in cases:
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent if result else None, intent)

    def test_classifier_and_llm_labels_map_to_player_documents(self):
        self.assertEqual(classify_intent("player_info", 0.8).filters, {"category": ["player"]})
        self.assertEqual(from_intent("player_info", 0.6).route, "football_rag")


class SeasonChanceTests(unittest.TestCase):
    def test_title_chance_without_mee_is_a_prediction(self):
        for query in ("โอกาสแชมป์ของอาร์เซนอล", "แล้วโอกาสแชมป์ของอาร์เซนอลล่ะ", "โอกาสตกชั้นของเบิร์นลีย์"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual((result.route, result.intent), ("local_ai", "prediction"))


class FollowUpWordingTests(unittest.TestCase):
    """Short and English questions that used to fall through to the classifier or land on trivia."""

    def intent(self, query):
        result = decide(query, CONTEXT, [], TEAMS)
        return result.intent if result else None

    def test_goal_count_and_scorer_questions_are_match_results(self):
        for query in ("นิวคาสเซิลยิงกี่ลูก", "ลิเวอร์พูลได้กี่ประตู", "เชลซียิงได้กี่ลูกเมื่อวาน", "ใครทำประตู",
                      "แล้วใครยิง", "who scored?", "who scored for Liverpool yesterday?",
                      "did Arsenal win?", "Who won Arsenal vs Chelsea yesterday?", "how did Chelsea do?"):
            with self.subTest(query=query):
                self.assertEqual(self.intent(query), "match_result")

    def test_next_match_questions_are_fixtures(self):
        for query in ("ลิเวอร์พูลนัดต่อไปเจอใคร", "ทีมนี้นัดต่อไปเตะกับใคร", "นัดถัดไปของเชลซีเตะเมื่อไหร่",
                      "อาร์เซนอลเจอใครต่อ", "when is the next match?", "who do Arsenal play next?",
                      "Chelsea next game"):
            with self.subTest(query=query):
                self.assertEqual(self.intent(query), "fixture_schedule")

    def test_top_of_the_table_is_standings(self):
        for query in ("who is top of the table?", "show me the league table"):
            with self.subTest(query=query):
                self.assertEqual(self.intent(query), "standings_stats")

    def test_records_and_history_stay_trivia(self):
        for query in ("ใครยิงแฮตทริกเร็วที่สุด", "ใครทำประตูมากที่สุดตลอดกาล", "ใครยิงประตูแรกในประวัติศาสตร์พรีเมียร์ลีก",
                      "who won the league in 2016", "who scored the fastest goal ever",
                      "ใครยิงให้ลิเวอร์พูลปี 2005", "who scored for Arsenal in 1998"):
            with self.subTest(query=query):
                self.assertEqual(self.intent(query), "trivia_history")

    def test_top_scorer_questions_keep_their_intent(self):
        for query in ("ใครยิงเยอะสุด", "who scored the most goals this season"):
            with self.subTest(query=query):
                self.assertEqual(self.intent(query), "standings_stats")


class InternationalTriviaTests(unittest.TestCase):
    """Thai golden set (eval/golden_thai.jsonl): World Cup, Euro and national-team questions
    are history, and their search text must not be pushed toward the Premier League."""

    def decide(self, query):
        return decide(query, CONTEXT, [], TEAMS)

    def test_international_scorer_questions_are_trivia(self):
        for query in ("ใครทำประตูแรกในบอลโลกอะ?",
                      "ผู้ยิงประตูได้เยอะที่สุดของทีมชาติโปแลนด์คือใคร?",
                      "ทีมชาติอังกฤษผู้ยิงประตูเยอะสุดคือใครอะ?",
                      "ใครเป็นผู้ทำประตูสูงสุดของทีมซัมเบียตลอดมา?",
                      "ใครทำประตูครบร้อยในลีกสูงสุดอังกฤษก่อนคนอื่น?"):
            with self.subTest(query=query):
                result = self.decide(query)
                self.assertEqual((result.route, result.intent), ("football_rag", "trivia_history"))
                self.assertNotIn("matchweek", result.filters)

    def test_competition_names_go_into_the_search_text(self):
        cases = [("ใครได้แชมป์บอลโลกปี 1954 นะ", ("FIFA World Cup", "1954")),
                 ("ทีมไหนแชมป์ยุโรป 88?", ("UEFA",)),
                 ("คอนเฟดคัพปี 2003 ใครได้แชมป์", ("Confederations Cup", "2003")),
                 ("ทีมที่เป็นรองชนะเลิศยูฟ่าแชมเปียนส์ลีกปี 1980 คือทีมไหน?", ("Champions League", "1980"))]
        for query, terms in cases:
            with self.subTest(query=query):
                rewritten = self.decide(query).rewritten_query
                for term in terms:
                    self.assertIn(term, rewritten)
                self.assertNotIn("Premier League", rewritten)
                self.assertIn(query, rewritten)

    def test_trivia_without_a_known_competition_keeps_the_question_alone(self):
        # A generic English prefix pulled the same unrelated documents to the top
        # (Thai golden set: raw Thai found them, the prefixed text did not).
        for query in ("ทีมไหนเคยแชมป์ทวีปตั้งแต่ครั้งแรกจนถึงครั้งที่ห้าต่อเนื่อง?",
                      "ทีมชาติที่ฉายาซูเปอร์อีเกิ้ลส์คือประเทศอะไร",
                      "ใครเป็นผู้ทำประตูสูงสุดของทีมซัมเบียตลอดมา?"):
            with self.subTest(query=query):
                self.assertEqual(self.decide(query).rewritten_query, query)

    def test_premier_league_title_text_is_short(self):
        count = self.decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง").rewritten_query
        self.assertEqual(count, "Arsenal Premier League title count อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง")
        # Without a team the Thai question already names the league; the prefix only hurt.
        query = "ทีมแรกที่ได้แชมป์พรีเมียร์ลีกโดยไม่ได้มาจากแมนเชสเตอร์หรือลอนดอนคือทีมไหน"
        self.assertEqual(self.decide(query).rewritten_query, query)

    def test_premier_league_questions_keep_their_routing(self):
        title = self.decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกกี่ครั้ง")
        self.assertEqual(title.intent, "trivia_history")
        self.assertIn("Premier League title", title.rewritten_query)
        self.assertEqual(self.decide("ใครยิงเยอะสุด").intent, "standings_stats")
        self.assertEqual(self.decide("ดาวซัลโวฟุตบอลโลกคือใคร").route, "decline")


if __name__ == "__main__":
    unittest.main()


class HistoricalDecisionTests(unittest.TestCase):
    def test_past_season_questions_search_the_archive_for_that_season(self):
        cases = (
            ("ใครได้แชมป์พรีเมียร์ลีกฤดูกาล 2004/05", "2004"),
            ("ฤดูกาล 98/99 ใครได้รองแชมป์พรีเมียร์ลีก", "1998"),
            ("ฤดูกาลที่แล้วใครได้แชมป์พรีเมียร์ลีก", "2025"),
            ("อาร์เซนอลจบอันดับเท่าไหร่ในฤดูกาล 2015/16", "2015"),
            ("เลสเตอร์ซิตี้ฤดูกาล 2015/16 ได้กี่แต้ม", "2015"),
            ("แบล็คเบิร์น โรเวอร์ส ฤดูกาล 1994/95 จบอันดับเท่าไหร่", "1994"),
            ("Bolton Wanderers 2005/06 final table position", "2005"),
            ("Who won the Premier League in 2004/05?", "2004"),
        )
        for query, season in cases:
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual((result.route, result.intent, result.layer),
                                 ("football_rag", "trivia_history", "rules"))
                self.assertEqual(result.filters, {"category": ["historical"], "season": season})

    def test_archive_search_names_teams_without_filtering_by_them(self):
        result = decide("อาร์เซนอลจบอันดับเท่าไหร่ในฤดูกาล 2015/16", CONTEXT, [], TEAMS)
        self.assertEqual(result.team_ids, [57])
        self.assertNotIn("team_ids", result.filters)
        self.assertIn("Premier League 2015/16 final table standings", result.rewritten_query)

    def test_head_to_head_questions_search_the_archive_without_a_season(self):
        for query in ("แมนยูเคยชนะลิเวอร์พูลกี่นัดในพรีเมียร์ลีก", "ลิเวอร์พูลกับเอฟเวอร์ตันเจอกันกี่ครั้ง",
                      "อาร์เซนอลกับเชลซี สถิติพบกันเป็นยังไง", "Arsenal vs Chelsea head to head"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertEqual(result.intent, "trivia_history")
                self.assertEqual(result.filters, {"category": ["historical"]})
                self.assertEqual(len(result.team_ids), 2)
        thai = decide("ลิเวอร์พูลกับเอฟเวอร์ตันเจอกันกี่ครั้ง", CONTEXT, [], TEAMS)
        self.assertIn("head-to-head", thai.rewritten_query)

    def test_season_label_crosses_the_century(self):
        result = decide("ฤดูกาล 1999/2000 ใครได้แชมป์พรีเมียร์ลีก", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters["season"], "1999")
        self.assertIn("1999/00", result.rewritten_query)

    def test_questions_the_archive_must_not_take(self):
        for query in ("อาร์เซนอลอยู่อันดับเท่าไหร่", "ตารางคะแนนพรีเมียร์ลีกฤดูกาล 2026/27",
                      "ตารางคะแนนปี 2026", "ตารางคะแนนฤดูกาล 2030/31", "อาร์เซนอลกับเชลซีใครจะชนะ",
                      "ใครได้แชมป์บอลโลกปี 1954", "ใครได้บัลลงดอร์ปี 2008", "ใครได้แชมป์เอฟเอคัพปี 2005",
                      "ใครได้แชมป์ยูฟ่าแชมเปียนส์ลีกปี 2005", "เมื่อวานอาร์เซนอลชนะไหม",
                      "ลิเวอร์พูลชนะไปกี่นัดแล้วฤดูกาลนี้", "อาร์เซนอลเคยชนะกี่นัดติด"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertNotEqual((result.filters if result else {}).get("category"), ["historical"])

    def test_without_a_current_season_past_years_are_not_assumed(self):
        self.assertIsNone(history_filters("ใครได้แชมป์ฤดูกาล 2004/05", 0, None))
        self.assertEqual(history_filters("อาร์เซนอลกับเชลซีสถิติพบกัน", 2, None),
                         {"category": ["historical"]})

    def test_other_history_searches_trivia_and_archive(self):
        self.assertEqual(classify_intent("trivia_history", 0.9).filters,
                         {"category": ["trivia", "historical"]})
        self.assertEqual(from_intent("trivia_history", 0.8).filters,
                         {"category": ["trivia", "historical"]})
        self.assertEqual(classify_intent("match_result", 0.9).filters, {"category": ["match_report"]})

    def test_nineties_short_season_for_scorers(self):
        self.assertEqual(historical_scorer_season("ดาวซัลโวพรีเมียร์ลีก 98/99", "2026"), ("1998", False))
        self.assertEqual(historical_scorer_season("ดาวซัลโวพรีเมียร์ลีก 24/25", "2026"), ("2024", False))

    def test_future_two_digit_seasons_are_not_last_century(self):
        self.assertEqual(historical_scorer_season("ดาวซัลโวฤดูกาล 27/28", "2026"), ("2027", False))
        for query in ("ตารางคะแนนฤดูกาล 27/28", "ใครแชมป์ฤดูกาล 27/28", "ตารางคะแนนฤดูกาล 30/31"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertNotEqual((result.filters if result else {}).get("category"), ["historical"])

    def test_current_match_questions_between_two_teams_stay_current(self):
        for query in ("แมนยูกับลิเวอร์พูลนัดล่าสุดชนะกันกี่ลูก", "แมนยูเจอลิเวอร์พูลเมื่อวานชนะกันกี่ประตู",
                      "แมนยูกับลิเวอร์พูลเจอกันกี่โมง", "แมนยูเจอลิเวอร์พูลเจอกันกี่ครั้งฤดูกาลนี้"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertNotEqual((result.filters if result else {}).get("category"), ["historical"])

    def test_other_competitions_never_search_only_the_league_archive(self):
        for query in ("แชมป์เอฟเอ คัพปี 2005", "แชมป์ถ้วยเอฟเอปี 2005", "แชมป์ efl cup ปี 2005",
                      "ใครแชมป์ไทยลีกปี 2010", "ใครแชมป์เอเชียนคัพปี 2007", "ใครได้แชมป์ซีเกมส์ปี 2005",
                      "ใครแชมป์ลีกกรีซฤดูกาล 2000/01", "บาร์เซโลน่าแชมป์ปี 2005"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertNotEqual((result.filters if result else {}).get("category"), ["historical"])

    def test_seasons_before_the_premier_league_keep_trivia(self):
        for query in ("ลิเวอร์พูลแชมป์ปี 1990", "ใครแชมป์ดิวิชั่น 4 ฤดูกาล 1991/92"):
            with self.subTest(query=query):
                result = decide(query, CONTEXT, [], TEAMS)
                self.assertNotEqual((result.filters if result else {}).get("category"), ["historical"])

    def test_a_bare_year_searches_both_seasons_it_may_mean(self):
        result = decide("อาร์เซนอลได้แชมป์พรีเมียร์ลีกปี 2004 ไหม", CONTEXT, [], TEAMS)
        self.assertEqual(result.filters, {"category": ["historical"]})
        self.assertIn("2003/04", result.rewritten_query)
        self.assertIn("2004/05", result.rewritten_query)
        self.assertNotIn("head-to-head", result.rewritten_query)

    def test_archive_search_names_former_clubs_in_english(self):
        cases = (("แบล็คเบิร์น โรเวอร์ส ฤดูกาล 1994/95 จบอันดับเท่าไหร่", "Blackburn Rovers"),
                 ("เลสเตอร์ซิตี้ฤดูกาล 2015/16 ได้กี่แต้ม", "Leicester City"))
        for query, name in cases:
            with self.subTest(query=query):
                self.assertIn(name, decide(query, CONTEXT, [], TEAMS).rewritten_query)


class ChatDecisionTests(unittest.TestCase):
    def test_chat_cases(self):
        cases = [json.loads(line) for line in CHAT_CASES.read_text(encoding="utf-8").splitlines() if line]
        self.assertGreaterEqual(len(cases), 40)
        for case in cases:
            with self.subTest(query=case["query"]):
                result = decide(case["query"], CONTEXT, [], TEAMS)
                if case["kind"]:
                    self.assertIsNotNone(result)
                    self.assertEqual((result.route, result.intent, result.layer, result.kind),
                                     ("chat", "chitchat", "rules", case["kind"]))
                    self.assertEqual(result.reasoning, f"คุยทั่วไป: {case['kind']}")
                    self.assertEqual(result.filters, {})
                else:
                    self.assertTrue(result is None or result.route != "chat")

    def test_gambling_and_off_topic_stay_declined(self):
        for query in ("คุณช่วยเรื่องพนันได้ไหม", "แนะนำทีเด็ดหน่อยคุณ", "อากาศวันนี้ร้อนไหม"):
            with self.subTest(query=query):
                self.assertEqual(decide(query, CONTEXT, [], TEAMS).route, "decline")

    def test_mixed_questions_keep_their_football_route(self):
        self.assertEqual(decide("สวัสดี ลิเวอร์พูลชนะไหม", CONTEXT, [], TEAMS).route, "football_rag")
        self.assertEqual(decide("ขอบคุณครับ ผลนัดล่าสุดล่ะ", CONTEXT, [], TEAMS).route, "football_rag")

    def test_chitchat_label_maps_to_chat_and_the_switch_restores_decline(self):
        self.assertEqual(INTENT_MAP["chitchat"], ("chat", None))
        self.assertEqual(classify_intent("chitchat", 0.9).route, "chat")
        self.assertEqual(classify_intent("chitchat", 0.9).filters, {})
        self.assertEqual(from_intent("chitchat", 0.6).route, "chat")
        with patch.dict("os.environ", {"ROUTER_CHAT_ENABLED": "false"}):
            self.assertIsNone(decide("สวัสดีครับ", CONTEXT, [], TEAMS))
            self.assertEqual(classify_intent("chitchat", 0.9).route, "decline")
            self.assertEqual(from_intent("chitchat", 0.6).intent, "out_of_scope")

    def test_misspelled_football_words_do_not_make_chat(self):
        result = decide("ผีเเดงเคยได้แชมร์กี่ปี", CONTEXT, [], TEAMS)
        self.assertNotEqual(result.route, "chat")
