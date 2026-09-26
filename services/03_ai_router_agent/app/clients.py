import json
import os
from uuid import uuid4

import httpx

from .router import UpstreamError


class ServiceClients:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http
        self.retrieval_url = os.getenv("RETRIEVAL_URL", "http://retrieval:8000").rstrip("/")
        self.engines_url = os.getenv("ENGINES_URL", "http://engines:8000").rstrip("/")
        self.generation_url = os.getenv("GENERATION_URL", "http://generation:8000").rstrip("/")
        self.football_data_url = os.getenv("FOOTBALL_DATA_URL", "http://football-data:8000").rstrip("/")

    async def get_teams(self):
        try:
            response = await self.http.get(self.football_data_url + "/football/teams",
                                           headers={"X-Request-ID": str(uuid4())}, timeout=3)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data.get("teams"), list) or not data["teams"]:
                raise ValueError("empty team directory")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamError("football-data") from exc

    async def _post(self, base: str, path: str, payload: dict, request_id: str, timeout: float, service: str):
        try:
            response = await self.http.post(base + path, json=payload,
                                            headers={"X-Request-ID": request_id}, timeout=timeout)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise UpstreamError(service) from exc
        if response.status_code >= 400:
            raise UpstreamError(service, response.status_code)
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("expected object")
            return data
        except ValueError as exc:
            raise UpstreamError(service) from exc

    async def search(self, payload: dict, request_id: str):
        return await self._post(self.retrieval_url, "/search", payload, request_id, 10, "retrieval")

    async def classify(self, payload: dict, request_id: str):
        return await self._post(self.engines_url, "/local/classify", payload, request_id, 25, "engines")

    async def general(self, payload: dict, request_id: str):
        return await self._post(self.engines_url, "/general", payload, request_id, 25, "engines")

    async def predict(self, payload: dict, request_id: str):
        return await self._post(self.engines_url, "/local/predict", payload, request_id, 25, "engines")

    async def generate(self, payload: dict, request_id: str):
        return await self._post(self.generation_url, "/generate", payload, request_id, 25, "generation")

    async def llm_decide(self, query: str, request_id: str):
        from openai import AsyncOpenAI

        system = ("Classify the user's Premier League football question. Return a JSON object with "
                  "intent (one of trivia_history, match_result, fixture_schedule, standings_stats, "
                  "weekly_summary, general_football, prediction, out_of_scope, clarify), "
                  "confidence (0 to 1), and rewritten_query (an English search query when factual). "
                  "Do not answer the question. Gambling and non-football requests are out_of_scope. "
                  "Ambiguous team or match references are clarify."
                  )
        providers = [
            ("GROQ_API_KEY", "GROQ_MODEL", "https://api.groq.com/openai/v1"),
            ("GEMINI_API_KEY", "GEMINI_MODEL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        ]
        for index, (key_name, model_name, base_url) in enumerate(providers):
            key = os.getenv(key_name)
            model = os.getenv(model_name)
            if not key or not model:
                continue
            try:
                client = AsyncOpenAI(api_key=key, base_url=base_url, timeout=8, max_retries=0)
                response = await client.chat.completions.create(
                    model=model, temperature=0,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": query}],
                    response_format={"type": "json_object"},
                    extra_headers={"X-Request-ID": request_id})
                data = json.loads(response.choices[0].message.content or "{}")
                if not isinstance(data, dict):
                    raise ValueError("invalid classification")
                data["fallback"] = "llm_fallback_provider" if index else None
                data["token_usage"] = {
                    "input": response.usage.prompt_tokens if response.usage else 0,
                    "output": response.usage.completion_tokens if response.usage else 0,
                }
                return data
            except Exception:
                continue
        raise UpstreamError("llm")
