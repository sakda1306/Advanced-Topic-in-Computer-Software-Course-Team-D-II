import asyncio
import time

from .decisions import decide, enrich, classify_intent, from_intent
from .teams import TeamDirectory


class UpstreamError(Exception):
    def __init__(self, service: str, status: int | None = None):
        super().__init__(f"{service}: {status or 'unavailable'}")
        self.service = service
        self.status = status


class Router:
    def __init__(self, clients, teams: TeamDirectory):
        self.clients = clients
        self.teams = teams

    async def route(self, request: dict) -> dict:
        start = time.monotonic()
        request_id = request["request_id"]
        query = request["query"]
        history = request.get("history", [])[-10:]
        user = request.get("user", {})
        context = request.get("context", {})
        trace = {"decided_at_layer": "guard", "intent": None, "rewritten_query": None,
                 "filters": {}, "fallback": None, "steps": []}
        engines = []
        usage = {"input": 0, "output": 0}

        def step(name, started):
            trace["steps"].append({"name": name, "ms": round((time.monotonic() - started) * 1000)})

        def add_usage(payload):
            part = payload.get("token_usage") or {}
            for key in usage:
                usage[key] += int(part.get(key) or 0)

        def finish(answer, route, confidence, reasoning, sources=None):
            return {"request_id": request_id, "answer": answer, "sources": sources or [],
                    "route": route, "engines_used": engines, "confidence": confidence,
                    "reasoning": reasoning, "latency_ms": round((time.monotonic() - start) * 1000),
                    "token_usage": usage, "trace": trace}

        try:
            async with asyncio.timeout(40):
                decided_at = time.monotonic()
                decision = decide(query, context, history, self.teams, user.get("favorite_team_id"))
                if decision is None:
                    try:
                        classify_at = time.monotonic()
                        raw = await self.clients.classify({"request_id": request_id, "text": query}, request_id)
                        step("engines.classify", classify_at)
                        data = raw.get("data") or {}
                        decision = classify_intent(data.get("label", ""), float(data.get("score") or 0))
                        if decision:
                            decision = enrich(decision, query, context, history, self.teams,
                                              user.get("favorite_team_id"))
                    except (UpstreamError, ValueError, TypeError):
                        trace["fallback"] = "classifier_down"
                if decision is None:
                    try:
                        llm_at = time.monotonic()
                        raw = await asyncio.wait_for(self.clients.llm_decide(query, request_id), timeout=8)
                        step("router.llm", llm_at)
                        add_usage(raw)
                        decision = from_intent(raw.get("intent", ""), float(raw.get("confidence") or 0.5))
                        if decision:
                            decision = enrich(decision, query, context, history, self.teams,
                                              user.get("favorite_team_id"))
                        if raw.get("fallback"):
                            trace["fallback"] = raw["fallback"]
                        if decision and raw.get("rewritten_query") and decision.route == "football_rag":
                            decision.rewritten_query = raw["rewritten_query"]
                    except (UpstreamError, ValueError, TypeError, asyncio.TimeoutError):
                        trace["fallback"] = "llm_unavailable"
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

                if decision.route == "football_rag":
                    chunks = []
                    retrieval_down = False
                    filters = dict(decision.filters)
                    payload = {"request_id": request_id, "query": decision.rewritten_query or query,
                               "query_original": query, "top_k": 5, "filters": filters, "mode": "hybrid"}
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
                        if chunks:
                            break
                        if attempt == 0 and any(key in filters for key in ("matchweek", "date_from", "date_to")):
                            filters = {key: value for key, value in filters.items()
                                       if key not in ("matchweek", "date_from", "date_to")}
                            payload = {**payload, "filters": filters}
                            trace["filters"] = filters
                        else:
                            break
                    if chunks:
                        contexts = [{"ref": index, "text": chunk["text"],
                                     "source": {**chunk["source"], "ref": index}}
                                    for index, chunk in enumerate(chunks[:5], 1)]
                        try:
                            generated_at = time.monotonic()
                            result = await self.clients.generate({"request_id": request_id, "mode": "grounded",
                                "query": query, "language": user.get("language", "th"), "contexts": contexts,
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
                    if len(decision.team_ids) != 2:
                        trace["fallback"] = "prediction_needs_two_teams"
                        return finish("กรุณาระบุสองทีมที่ต้องการทำนายผล", "clarify", decision.confidence,
                                      decision.reasoning)
                    try:
                        predict_at = time.monotonic()
                        result = await self.clients.predict({"request_id": request_id,
                            "home_team_id": decision.team_ids[0], "away_team_id": decision.team_ids[1],
                            "season": str(context.get("season", ""))}, request_id)
                        step("engines.predict", predict_at)
                        engines.append("local_ai")
                        add_usage(result)
                    except UpstreamError as exc:
                        trace["fallback"] = "prediction_unavailable"
                        answer = "ฟีเจอร์ทำนายผลยังไม่เปิดใช้งาน" if exc.status == 501 else "ตอนนี้ระบบทำนายผลไม่พร้อมใช้งาน"
                        return finish(answer, "local_ai", decision.confidence, decision.reasoning)
                else:
                    try:
                        general_at = time.monotonic()
                        result = await self.clients.general({"request_id": request_id, "query": query,
                            "history": history, "language": user.get("language", "th")}, request_id)
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
