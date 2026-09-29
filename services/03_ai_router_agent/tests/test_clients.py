import asyncio
import unittest
from unittest.mock import patch

import httpx

from app.clients import ServiceClients
from app.router import UpstreamError


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_only_is_not_labeled_fallback(self):
        class FakeCompletions:
            async def create(self, **kwargs):
                return type("Response", (), {
                    "choices": [type("Choice", (), {"message": type("Message", (), {
                        "content": '{"intent": "trivia_history", "confidence": 0.9}'})()})()],
                    "usage": None})()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        with patch.dict("os.environ", {"GROQ_API_KEY": "", "GROQ_MODEL": "",
                                    "GEMINI_API_KEY": "test", "GEMINI_MODEL": "test"}), \
             patch("openai.AsyncOpenAI", FakeOpenAI):
            result = await ServiceClients(None).llm_decide("question", "req")
        self.assertIsNone(result["fallback"])

    async def test_gemini_is_tried_after_groq_stalls(self):
        calls = []

        class FakeCompletions:
            def __init__(self, provider):
                self.provider = provider

            async def create(self, **kwargs):
                calls.append(self.provider)
                if self.provider == "groq":
                    await asyncio.sleep(1)
                return type("Response", (), {
                    "choices": [type("Choice", (), {"message": type("Message", (), {
                        "content": '{"intent": "trivia_history", "confidence": 0.9}'})()})()],
                    "usage": None})()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                provider = "groq" if "groq.com" in kwargs["base_url"] else "gemini"
                self.chat = type("Chat", (), {"completions": FakeCompletions(provider)})()

        with patch.dict("os.environ", {"GROQ_API_KEY": "test", "GROQ_MODEL": "test",
                                    "GEMINI_API_KEY": "test", "GEMINI_MODEL": "test"}), \
             patch("openai.AsyncOpenAI", FakeOpenAI), \
             patch("app.clients.LLM_PROVIDER_TIMEOUT", 0.01, create=True):
            result = await asyncio.wait_for(ServiceClients(None).llm_decide("question", "req"), 0.5)
        self.assertEqual(calls, ["groq", "gemini"])
        self.assertEqual(result["fallback"], "llm_fallback_provider")

    async def test_invalid_team_payload_uses_upstream_fallback(self):
        for payload in ([{"team_id": 1}], {"teams": [{"team_id": "bad", "name": "A",
                                                        "short_name": "A"}]}):
            with self.subTest(payload=payload):
                async def handler(request):
                    return httpx.Response(200, json=payload)

                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
                    with self.assertRaises(UpstreamError):
                        await ServiceClients(http).get_teams()


if __name__ == "__main__":
    unittest.main()
