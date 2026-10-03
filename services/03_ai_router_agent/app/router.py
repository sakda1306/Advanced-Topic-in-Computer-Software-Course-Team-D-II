import asyncio
import time

from .chat import STEP_TIMEOUT as CHAT_STEP_TIMEOUT
from .chat import favorite_name, system_prompt, template, user_message, validate_reply
from .condense import _strict, condense_enabled, needs_condense, rules_resolved, validate
from .decisions import (HISTORICAL, MATCHWEEK_PATTERN, classify_intent, decide, enrich, from_intent,
                        historical_scorer_season, league_wide_scorer_query, normalize_thai,
                        prediction_kind)
from .prediction_text import (NEEDS_TEAM_TEXT, TEAM_NOT_FOUND_TEXT, UNAVAILABLE_TEXT,
                              match_prediction_text, simulation_focus, summarize_simulation)
from .teams import TeamDirectory
from .translate import fuse, multi_query_enabled, needs_translation, validate_translation


CONDENSE_TIMEOUT = 4
TRANSLATE_TIMEOUT = 4


class UpstreamError(Exception):
    def __init__(self, service: str, status: int | None = None):
        super().__init__(f"{service}: {status or 'unavailable'}")
        self.service = service
        self.status = status


def with_team_note(query: str, teams: TeamDirectory, language: str) -> str:
    """The question for an LLM step, naming the club behind each nickname.

    The LLMs have no team directory: /general mixed up ผีแดง (Man United) with หงส์แดง (Liverpool),
    grounded generation answered หงส์แดง with Man United's row of the table, and the classifier called
    ผึ้งแดง (Brentford) out of scope. Short Thai aliases such as ผี stay unnamed.
    """
    named = _strict(teams).nicknames(query)
    if not named:
        return query
    label = "ชื่อทีมในคำถาม" if language == "th" else "Teams named in the question"
    pairs = ", ".join(f"{written} = {team.name}" for written, team in named)
    return f"{query}\n({label}: {pairs})"


class Router:
    def __init__(self, clients, teams: TeamDirectory):
        self.clients = clients
        self.teams = teams

    async def route(self, request: dict) -> dict:
        start = time.monotonic()
        request_id = request["request_id"]
        query = normalize_thai(request["query"])
        history = [{**item, "content": normalize_thai(str(item.get("content") or ""))}
                   for item in request.get("history", [])[-10:]]
        user = request.get("user", {})
        context = request.get("context", {})
        trace = {"decided_at_layer": "guard", "intent": None, "rewritten_query": None,
                 "standalone_query": None, "condense": None,
                 "search_query_en": None, "multi_query": None, "chat": None,
                 "filters": {}, "fallback": None, "steps": []}
        engines = []
        usage = {"input": 0, "output": 0}

        def step(name, started):
            trace["steps"].append({"name": name, "ms": round((time.monotonic() - started) * 1000)})

        def add_usage(payload):
            part = payload.get("token_usage") or {}
            for key in usage:
                usage[key] += int(part.get(key) or 0)

        async def english_query(text):
            translate_at = time.monotonic()
            try:
                raw = await asyncio.wait_for(self.clients.translate(text, request_id),
                                             timeout=TRANSLATE_TIMEOUT)
            except (UpstreamError, ValueError, TypeError, asyncio.TimeoutError):
                trace["multi_query"] = "unavailable"
                return None
            finally:
                step("router.translate", translate_at)
            add_usage(raw)
            checked = validate_translation(text, str(raw.get("query") or ""), self.teams)
            trace["multi_query"] = "applied" if checked else "rejected"
            trace["search_query_en"] = checked
            return checked

        def finish(answer, route, confidence, reasoning, sources=None):
            return {"request_id": request_id, "answer": answer, "sources": sources or [],
                    "route": route, "engines_used": engines, "confidence": confidence,
                    "reasoning": reasoning, "latency_ms": round((time.monotonic() - start) * 1000),
                    "token_usage": usage, "trace": trace}

        try:
            async with asyncio.timeout(40):
                routing_query = query
                original = decide(query, context, history, self.teams, user.get("favorite_team_id"))
                # Declines, chat replies and clarifying guards stand as asked; a rewrite must never talk past them.
                guarded = original is not None and (
                    original.route in ("decline", "chat") or original.layer == "guard")
                # Spend the LLM budget only when the rules have not already found the intent and its team.
                if (not guarded and not rules_resolved(original) and condense_enabled()
                        and needs_condense(query, history, self.teams, context.get("season"))):
                    condense_at = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(self.clients.condense(query, history, request_id),
                                                     timeout=CONDENSE_TIMEOUT)
                        add_usage(raw)
                        checked = validate(query, str(raw.get("standalone_query") or ""), history, self.teams)
                        if checked is None:
                            trace["condense"] = "rejected"
                        elif checked == query:
                            trace["condense"] = "unchanged"
                        else:
                            trace["condense"] = "applied"
                            routing_query = checked
                    except (UpstreamError, ValueError, TypeError, asyncio.TimeoutError):
                        trace["condense"] = "unavailable"
                    step("router.condense", condense_at)

                decided_at = time.monotonic()
                decision = original
                if routing_query != query:
                    decision = decide(routing_query, context, history, self.teams, user.get("favorite_team_id"))
                    if decision is None and original is not None:
                        # The rules know the original follow-up but not its rewrite: keep the original.
                        decision, routing_query = original, query
                trace["standalone_query"] = routing_query if routing_query != query else None
                historical_scorer = historical_scorer_season(routing_query, context.get("season"))
                if (historical_scorer and league_wide_scorer_query(routing_query, self.teams)
                        and (decision is None or decision.route == "football_rag")):
                    season, assumed = historical_scorer
                    season_label = f"{season}/{(int(season) + 1) % 100:02d}"
                    trace.update(decided_at_layer="rules", intent="trivia_history",
                                 rewritten_query=f"Premier League {season_label} top scorer",
                                 filters={"season": season, "source": "official_scorer_reference"})
                    step("router.rules", decided_at)
                    try:
                        source_at = time.monotonic()
                        record = await self.clients.historical_scorer(season, request_id)
                        step("football_data.verified_scorer", source_at)
                        engines.append("football_data")
                    except UpstreamError as exc:
                        trace["fallback"] = "historical_scorer_unavailable"
                        if exc.status == 404:
                            return finish(f"ยังไม่มีข้อมูลดาวซัลโวพรีเมียร์ลีกฤดูกาล {season_label} ที่ตรวจสอบได้ในระบบ",
                                          "football_rag", 0.9, "ไม่มีแหล่งอันดับดาวซัลโวที่ยืนยันได้")
                        return finish("ตอนนี้ระบบข้อมูลย้อนหลังไม่พร้อมใช้งาน ลองใหม่อีกครั้งในภายหลัง",
                                      "football_rag", 0.9, "แหล่งข้อมูลย้อนหลังไม่พร้อมใช้งาน")
                    if record["season"] != season or not isinstance(record["goals"], int):
                        trace["fallback"] = "historical_scorer_invalid"
                        return finish("ข้อมูลดาวซัลโวย้อนหลังไม่ตรงกับฤดูกาลที่ถาม",
                                      "football_rag", 0.0, "ข้อมูลต้นทางไม่ถูกต้อง")
                    source = {"ref": 1, "doc_id": f"official-scorer-{season}",
                              "title": f"Premier League Golden Boot {season_label}",
                              "category": "historical", "origin": "premierleague.com",
                              "season": season, "matchweek": None, "team_ids": [],
                              "fetched_at": None, "url": record["source_url"]}
                    prefix = "ถ้าหมายถึงพรีเมียร์ลีกฤดูกาล" if assumed else "พรีเมียร์ลีกฤดูกาล"
                    answer = f"{prefix} {season_label} ดาวซัลโวคือ {record['player']} ทำ {record['goals']} ประตู [1]"
                    return finish(answer, "football_rag", 0.95,
                                  "อันดับดาวซัลโวจากแหล่งพรีเมียร์ลีกที่ตรวจสอบแล้ว", [source])
                if decision is None:
                    try:
                        classify_at = time.monotonic()
                        raw = await self.clients.classify({"request_id": request_id, "text": routing_query}, request_id)
                        step("engines.classify", classify_at)
                        data = raw.get("data") or {}
                        decision = classify_intent(data.get("label", ""), float(data.get("score") or 0))
                        if decision:
                            decision = enrich(decision, routing_query, context, history, self.teams,
                                              user.get("favorite_team_id"))
                    except (UpstreamError, ValueError, TypeError):
                        trace["fallback"] = "classifier_down"
                if decision is None:
                    try:
                        llm_at = time.monotonic()
                        noted = with_team_note(routing_query, self.teams, user.get("language", "th"))
                        raw = await asyncio.wait_for(self.clients.llm_decide(noted, request_id), timeout=8)
                        step("router.llm", llm_at)
                        add_usage(raw)
                        decision = from_intent(raw.get("intent", ""), float(raw.get("confidence") or 0.5))
                        if decision:
                            decision = enrich(decision, routing_query, context, history, self.teams,
                                              user.get("favorite_team_id"))
                        if raw.get("fallback"):
                            trace["fallback"] = raw["fallback"]
                        if decision and raw.get("rewritten_query") and decision.route == "football_rag":
                            rewritten = str(raw["rewritten_query"]).strip()
                            decision.rewritten_query = (rewritten if routing_query in rewritten else
                                                        f"{rewritten} {routing_query}".strip())
                    except (UpstreamError, ValueError, TypeError, asyncio.TimeoutError):
                        trace["fallback"] = "llm_unavailable"
                if (decision is not None and decision.route == "decline" and decision.layer != "guard"
                        and _strict(self.teams).find(routing_query)):
                    # The rules already decline gambling and other topics; a model calling a question about
                    # a clearly named club out of scope did not know the club.
                    decision = enrich(from_intent("general_football", decision.confidence, decision.layer),
                                      routing_query, context, history, self.teams, user.get("favorite_team_id"))
                    decision.reasoning += " (ถามถึงทีมพรีเมียร์ลีก)"
                if decision is None:
                    decision = from_intent("clarify", 0.5, "guard")
                    decision.reasoning = "ยังระบุเจตนาของคำถามไม่ได้"
                step(f"router.{decision.layer}", decided_at)
                trace.update(decided_at_layer=decision.layer, intent=decision.intent,
                             rewritten_query=decision.rewritten_query, filters=decision.filters)

                if decision.route == "clarify":
                    answer = ("หมายถึงทีมใดหรือแมตช์ไหนครับ ช่วยระบุชื่อทีมเต็มหรือช่วงเวลาอีกนิด"
                              if user.get("language", "th") == "th" else
                              "Which team or match do you mean? Please specify the full team name or date.")
                    return finish(answer, decision.route, decision.confidence, decision.reasoning)
                if decision.route == "decline":
                    answer = ("ผมช่วยตอบคำถามเกี่ยวกับฟุตบอลพรีเมียร์ลีกได้ แต่ไม่สามารถช่วยเรื่องนี้ได้"
                              if user.get("language", "th") == "th" else
                              "I can help with Premier League football questions, but not this request.")
                    return finish(answer, decision.route, decision.confidence, decision.reasoning)

                if decision.route == "chat":
                    kind = decision.kind or "other"
                    language = user.get("language", "th")
                    favorite = favorite_name(self.teams, user.get("favorite_team_id"))
                    answer = None
                    if kind != "internals":  # instructions are never put in front of the LLM again
                        chat_at = time.monotonic()
                        try:
                            raw = await asyncio.wait_for(
                                self.clients.chat(system_prompt(language, favorite),
                                                  user_message(history, query, kind), request_id),
                                timeout=CHAT_STEP_TIMEOUT)
                            add_usage(raw)
                            answer = validate_reply(raw.get("reply"), query, language, self.teams, favorite, kind)
                            trace["chat"] = "applied" if answer else "rejected"
                        except (UpstreamError, ValueError, TypeError, asyncio.TimeoutError):
                            trace["chat"] = "unavailable"
                        step("router.chat", chat_at)
                    return finish(answer or template(kind, language), "chat", decision.confidence,
                                  decision.reasoning)

                if decision.route == "football_rag":
                    chunks = []
                    retrieval_down = False
                    filters = dict(decision.filters)
                    payload = {"request_id": request_id, "query": decision.rewritten_query or routing_query,
                               "query_original": query, "top_k": 5, "filters": filters, "mode": "hybrid"}
                    english_task = None
                    english = None
                    # Archive searches already carry an English season rewrite; a free translation
                    # pulls look-alike team-season chunks over the answer (CONTRACT v1.11).
                    if (multi_query_enabled() and needs_translation(routing_query)
                            and filters.get("category") != [HISTORICAL]):
                        english_task = asyncio.create_task(english_query(routing_query))
                    for attempt in range(2):
                        try:
                            search_at = time.monotonic()
                            result = await self.clients.search(payload, request_id)
                            step("retrieval.search", search_at)
                            if "retrieval" not in engines:
                                engines.append("retrieval")
                            chunks = result.get("chunks") or []
                        except UpstreamError:
                            retrieval_down = True
                            break
                        if english_task is not None:
                            english = await english_task
                            english_task = None
                        if english:
                            try:
                                search_en_at = time.monotonic()
                                extra = await self.clients.search({**payload, "query": english},
                                                                  request_id)
                                step("retrieval.search_en", search_en_at)
                                chunks = fuse(chunks, extra.get("chunks") or [])
                            except UpstreamError:
                                pass  # the first search still answers
                        if chunks:
                            break
                        explicit_standings_week = (
                            decision.intent == "standings_stats"
                            and MATCHWEEK_PATTERN.search(routing_query.lower()) is not None
                        )
                        if (
                            attempt == 0
                            and not explicit_standings_week
                            and any(key in filters for key in ("matchweek", "date_from", "date_to"))
                        ):
                            filters = {key: value for key, value in filters.items()
                                       if key not in ("matchweek", "date_from", "date_to")}
                            payload = {**payload, "filters": filters}
                            trace["filters"] = filters
                        else:
                            break
                    if english_task is not None:  # the first search failed before we waited for it
                        english_task.cancel()
                    if chunks:
                        contexts = [{"ref": index, "text": chunk["text"],
                                     "source": {**chunk["source"], "ref": index}}
                                    for index, chunk in enumerate(chunks[:5], 1)]
                        try:
                            generated_at = time.monotonic()
                            language = user.get("language", "th")
                            result = await self.clients.generate({"request_id": request_id, "mode": "grounded",
                                "query": with_team_note(query, self.teams, language), "language": language,
                                "contexts": contexts,
                                "scope_team_ids": decision.team_ids,
                                "draft": None, "history": history}, request_id)
                            step("generation.grounded", generated_at)
                            engines.append("generation")
                            add_usage(result)
                            return finish(result["answer"], decision.route, decision.confidence,
                                          decision.reasoning, result.get("sources") or [])
                        except UpstreamError:
                            trace["fallback"] = "generation_down"
                            return finish("ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่", decision.route,
                                          decision.confidence, decision.reasoning)
                    trace["fallback"] = "retrieval_down" if retrieval_down else "retrieval_empty"
                    if decision.filters.get("category") == [HISTORICAL]:
                        # Archive statistics: a general answer would invent the numbers.
                        return finish("ยังไม่มีข้อมูลสถิติย้อนหลังนี้ในระบบ", decision.route,
                                      decision.confidence, decision.reasoning)
                    if decision.intent != "trivia_history":
                        latest = context.get("last_ingest_at")
                        suffix = f" ข้อมูลล่าสุด ณ {latest}" if latest else ""
                        return finish("ยังไม่มีข้อมูลของช่วงนี้ในระบบ" + suffix, decision.route,
                                      decision.confidence, decision.reasoning)
                    decision.route = "general_ai"
                    caveat = " คำตอบนี้มาจากความรู้ทั่วไป ไม่ได้อ้างอิงคลังข้อมูล"
                else:
                    caveat = ""

                if decision.route == "local_ai":
                    kind = prediction_kind(routing_query, decision.team_ids)
                    if kind == "needs_team":
                        trace["fallback"] = "prediction_needs_team"
                        return finish(NEEDS_TEAM_TEXT, "clarify", decision.confidence, decision.reasoning)
                    try:
                        predict_at = time.monotonic()
                        if kind == "match":
                            prediction = await self.clients.predict_match(
                                decision.team_ids[0], decision.team_ids[1], request_id)
                            step("football_data.predict", predict_at)
                            draft = match_prediction_text(prediction)
                        else:
                            snapshot = await self.clients.season_simulation(request_id)
                            step("football_data.simulation", predict_at)
                            draft = summarize_simulation(snapshot, simulation_focus(routing_query),
                                                         decision.team_ids)
                        engines.append("local_ai")
                    except UpstreamError as exc:
                        if kind == "match" and exc.status == 404:
                            trace["fallback"] = "prediction_team_not_found"
                            return finish(TEAM_NOT_FOUND_TEXT, "local_ai", decision.confidence,
                                          decision.reasoning)
                        trace["fallback"] = "simulation_down"
                        return finish(UNAVAILABLE_TEXT, "local_ai", decision.confidence, decision.reasoning)
                    result = {"content": draft}
                else:
                    try:
                        general_at = time.monotonic()
                        language = user.get("language", "th")
                        result = await self.clients.general({"request_id": request_id,
                            "query": with_team_note(query, self.teams, language),
                            "history": history, "language": language}, request_id)
                        step("engines.general", general_at)
                        engines.append("general_ai")
                        add_usage(result)
                    except UpstreamError:
                        trace["fallback"] = "general_down"
                        return finish("ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่", "general_ai",
                                      decision.confidence, decision.reasoning)
                try:
                    generated_at = time.monotonic()
                    generated = await self.clients.generate({"request_id": request_id,
                        "mode": "passthrough", "query": query, "language": user.get("language", "th"),
                        "contexts": [], "draft": result.get("content", ""), "history": history}, request_id)
                    step("generation.passthrough", generated_at)
                    engines.append("generation")
                    add_usage(generated)
                    return finish(generated["answer"] + caveat, decision.route, decision.confidence,
                                  decision.reasoning, generated.get("sources") or [])
                except UpstreamError:
                    trace["fallback"] = "generation_down"
                    return finish("ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่", decision.route,
                                  decision.confidence, decision.reasoning)
        except asyncio.TimeoutError:
            trace["fallback"] = "router_timeout"
            return finish("ตอนนี้ระบบไม่ว่าง ลองใหม่อีกครั้งในอีกสักครู่", "clarify", 0.0,
                          "เกินเวลาตอบกลับของ router")
