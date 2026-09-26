import unittest

from app.router import Router, UpstreamError
from app.teams import TeamDirectory
from pathlib import Path


class FakeClients:
    def __init__(self):
        self.calls = []
        self.chunks = []
        self.classifier = {"data": {"label": "general_football", "score": 0.9}}

    async def search(self, payload, request_id):
        self.calls.append(("search", payload, request_id))
        return {"chunks": self.chunks}

    async def general(self, payload, request_id):
        self.calls.append(("general", payload, request_id))
        return {"content": "กฎฟุตบอล", "token_usage": {"input": 2, "output": 3}}

    async def classify(self, payload, request_id):
        self.calls.append(("classify", payload, request_id))
        return self.classifier

    async def predict(self, payload, request_id):
        self.calls.append(("predict", payload, request_id))
        return {"content": "ทีมเหย้า 40%", "token_usage": {"input": 0, "output": 0}}

    async def generate(self, payload, request_id):
        self.calls.append(("generate", payload, request_id))
        return {"answer": "ตอบแล้ว", "sources": [c["source"] for c in payload.get("contexts", [])],
                "token_usage": {"input": 5, "output": 7}}

    async def llm_decide(self, query, request_id):
        self.calls.append(("llm", query, request_id))
        return {"intent": "general_football", "confidence": 0.8}


class RouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clients = FakeClients()
        teams = TeamDirectory.from_file(Path(__file__).parents[1] / "data" / "team_aliases.json")
        self.router = Router(self.clients, teams)
        self.request = {"request_id": "req-1", "session_id": "session-1",
                        "user": {"id": "user-1", "favorite_team_id": None, "language": "th"},
                        "query": "", "history": [],
                        "context": {"season": "2026", "current_matchweek": 5,
                                    "now": "2026-09-26T10:00:00+07:00"}}

    async def run_query(self, query):
        return await self.router.route({**self.request, "query": query})

    async def test_rag_calls_search_and_grounded_generation(self):
        source = {"ref": 1, "doc_id": "match-1", "title": "Arsenal result", "category": "match_report",
                  "origin": "football-data.org", "season": "2026", "matchweek": 5,
                  "team_ids": [57], "fetched_at": "2026-09-26T09:00:00+07:00", "url": None}
        self.clients.chunks = [{"text": "Arsenal won 1-0", "source": source}]
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["engines_used"], ["retrieval", "generation"])
        self.assertEqual(self.clients.calls[0][0], "search")
        self.assertEqual(self.clients.calls[0][1]["filters"]["team_ids"], [57])
        self.assertEqual(self.clients.calls[1][1]["mode"], "grounded")
        self.assertTrue(all(call[2] == "req-1" for call in self.clients.calls))

    async def test_empty_match_data_never_calls_general(self):
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["route"], "football_rag")
        self.assertEqual(result["trace"]["fallback"], "retrieval_empty")
        self.assertEqual([x[0] for x in self.clients.calls], ["search", "search"])

    async def test_empty_trivia_falls_back_to_general(self):
        result = await self.run_query("ใครได้บัลลงดอร์ปี 2008")
        self.assertEqual(result["route"], "general_ai")
        self.assertIn("ไม่ได้อ้างอิงคลังข้อมูล", result["answer"])
        self.assertEqual([x[0] for x in self.clients.calls], ["search", "general", "generate"])

    async def test_ambiguous_team_does_not_call_upstream(self):
        result = await self.run_query("ยูไนเต็ดนัดล่าสุดชนะไหม")
        self.assertEqual(result["route"], "clarify")
        self.assertEqual(self.clients.calls, [])

    async def test_unknown_uses_classifier(self):
        result = await self.run_query("ฟุตบอลเล่นกี่คน")
        self.assertEqual(result["trace"]["decided_at_layer"], "classifier")
        self.assertEqual([x[0] for x in self.clients.calls], ["classify", "general", "generate"])

    async def test_low_classifier_uses_llm(self):
        self.clients.classifier = {"data": {"label": "general_football", "score": 0.4}}
        result = await self.run_query("ฟุตบอลเล่นกี่คน")
        self.assertEqual(result["trace"]["decided_at_layer"], "llm")

    async def test_prediction_501_returns_contract_message(self):
        async def unavailable(payload, request_id):
            raise UpstreamError("engines", 501)
        self.clients.predict = unavailable
        result = await self.run_query("ทำนายผล แมนซิตี้ กับ ลิเวอร์พูล")
        self.assertEqual(result["route"], "local_ai")
        self.assertEqual(result["answer"], "ฟีเจอร์ทำนายผลยังไม่เปิดใช้งาน")

    async def test_retrieval_down_never_invents_match_result(self):
        async def unavailable(payload, request_id):
            raise UpstreamError("retrieval", 503)
        self.clients.search = unavailable
        result = await self.run_query("เมื่อวานปืนใหญ่ชนะไหม")
        self.assertEqual(result["trace"]["fallback"], "retrieval_down")
        self.assertEqual(result["engines_used"], [])
        self.assertNotIn("general", [call[0] for call in self.clients.calls])

    async def test_generation_down_does_not_expose_unchecked_draft(self):
        async def unavailable(payload, request_id):
            raise UpstreamError("generation", 503)
        self.clients.generate = unavailable
        result = await self.run_query("อธิบายกฎล้ำหน้า")
        self.assertEqual(result["trace"]["fallback"], "generation_down")
        self.assertEqual(result["answer"], "ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่")


if __name__ == "__main__":
    unittest.main()
