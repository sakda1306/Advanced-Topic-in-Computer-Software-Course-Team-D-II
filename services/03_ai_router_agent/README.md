# 03 AI Router Agent

FastAPI router for the Premier League Football Assistant. It implements `docs/CONTRACT.md` §2–5 without changing neighboring services.

## Routes

`POST /route` selects `football_rag`, `general_ai`, `local_ai`, `clarify`, or `decline`. Decisions run through guards, rules, the `/local/classify` engine (score at least 0.75), and finally a structured LLM decision. The LLM uses Groq first and Gemini once as a fallback. Rule decisions report confidence `0.9`; classifier and LLM decisions report their own score.

The router maps team names and Thai nicknames to football-data.org team IDs, resolves simple follow-ups from recent user history, and turns relative dates into search filters. It refreshes the team list from 07 every five minutes. `data/team_aliases.json` supplies the initial and offline list.

For factual answers it searches 05 and passes the retrieved contexts to 06. Thai search rewrites keep the entire original question alongside English search hints so names and conditions reach 05. An empty filtered search is retried once without temporal filters. Trivia can fall back to General AI with an explicit caveat; match results, fixtures, standings, and weekly reports never do. General and local engine drafts pass through 06. A 501 prediction response becomes the contracted unavailable message. Every response includes route confidence, trace, latency, and token usage.

## Run

From this directory:

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Set `RETRIEVAL_URL`, `ENGINES_URL`, `GENERATION_URL`, and `FOOTBALL_DATA_URL` when the services do not use the Compose hostnames (`http://retrieval:8000`, `http://engines:8000`, `http://generation:8000`, `http://football-data:8000`). To enable the LLM decision layer, set `GROQ_API_KEY` and `GROQ_MODEL`; optionally set `GEMINI_API_KEY` and `GEMINI_MODEL` for fallback. No key is required for guard and rule decisions.

Run the offline tests with `python -m unittest discover -s tests -v`. Run `python eval_routes.py` for the measured 40-case router evaluation (eight examples per route). It prints `total`, `correct`, `route_accuracy`, and failures; a mismatch exits with code 1. This benchmark uses deterministic replies for 04/05/06, so its accuracy measures routing of these examples, not live answer quality. The test suite also covers HTTP request and response shapes with mocked upstream services, source forwarding, 501 prediction, 503 retrieval, and router timeout.

## Integration checkpoints

- 02 calls `POST /route` at the router service URL and sends `X-Request-ID`.
- 04 provides `/general`, `/local/classify`, and optionally `/local/predict` at the configured Engines URL.
- 05 provides `/search` at the Retrieval URL.
- 06 provides `/generate` at the Generation URL.
- 07 provides `/football/teams`; the local alias list is used while 07 is unavailable.
- For an empty live-data search, 02 should include optional `context.last_ingest_at` from 07 status so the fallback answer can show the latest ingest time. The current 02 request schema sends only season, matchweek, and now, so 03 does not invent a timestamp when it is absent.
- Scorer questions use the `standings` category required by `docs/CONTRACT.md` §4. A factual scorer answer depends on 07 publishing scorer data in the indexed standings document and 05 returning it.

The deploy owner supplies the service container and Compose wiring. This module contains only the router implementation and its own tests.
