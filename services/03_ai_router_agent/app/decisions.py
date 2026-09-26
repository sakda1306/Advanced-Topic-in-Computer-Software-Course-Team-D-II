import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .teams import TeamDirectory


INTENT_MAP = {
    "trivia_history": ("football_rag", "trivia"),
    "match_result": ("football_rag", "match_report"),
    "fixture_schedule": ("football_rag", "fixtures"),
    "standings_stats": ("football_rag", "standings"),
    "weekly_summary": ("football_rag", "weekly_report"),
    "general_football": ("general_ai", None),
    "prediction": ("local_ai", None),
    "out_of_scope": ("decline", None),
}


@dataclass
class Decision:
    route: str
    intent: str | None
    layer: str
    confidence: float
    reasoning: str
    filters: dict = field(default_factory=dict)
    rewritten_query: str | None = None
    team_ids: list[int] = field(default_factory=list)


def classify_intent(label: str, score: float) -> Decision | None:
    if label not in INTENT_MAP or score < 0.75:
        return None
    route, category = INTENT_MAP[label]
    filters = {"category": [category]} if category else {}
    return Decision(route, label, "classifier", score, f"classifier: {label}", filters)


def from_intent(label: str, confidence: float, layer: str = "llm") -> Decision | None:
    confidence = min(1.0, max(0.0, confidence))
    if label == "clarify":
        return Decision("clarify", None, layer, confidence, "คำถามกำกวม")
    if label not in INTENT_MAP:
        return None
    decision = classify_intent(label, max(0.75, confidence))
    decision.confidence = confidence
    decision.layer = layer
    decision.reasoning = f"{layer}: {label}"
    return decision


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _intent(query: str) -> str | None:
    text = query.lower()
    if _has(text, ("พนัน", "เดิมพัน", "ราคาบอล", "ทีเด็ด", "แทงบอล", "odds", "betting", "bet ")):
        return "out_of_scope"
    if _has(text, ("อากาศ", "ร้านอาหาร", "bitcoin", "โค้ด python", "เขียนเว็บ", "หุ้น")):
        return "out_of_scope"
    if _has(text, ("ทำนาย", "คาดการณ์", "พยากรณ์ผล", "predict", "who will win", "โอกาสชนะ", "น่าจะชนะ")):
        return "prediction"
    if _has(text, ("กฎ", "ล้ำหน้า", "var ", "ใบเหลือง", "ใบแดง", "แฮนด์บอล", "ลูกโทษ", "แผนการเล่น", "free kick", "ผู้รักษาประตูใช้มือ")):
        return "general_football"
    if _has(text, ("สรุป", "ไฮไลต์", "weekly summary")) and _has(text, ("สัปดาห์", "นัด", "week", "พรีเมียร์ลีก")):
        return "weekly_summary"
    if _has(text, ("โปรแกรม", "เตะกับใครต่อ", "แข่งกับใครต่อ", "นัดหน้า", "เมื่อไร", "วันไหน", "fixture", "schedule")):
        return "fixture_schedule"
    if _has(text, ("ตารางคะแนน", "จ่าฝูง", "อันดับ", "กี่แต้ม", "ดาวซัลโว", "standings", "points")):
        return "standings_stats"
    if _has(text, ("เมื่อวาน", "นัดล่าสุด", "นัดก่อน", "ชนะไหม", "ผลนัด", "ผลแข่ง", "จบเท่าไร", "สกอร์", "score", "result")):
        return "match_result"
    if _has(text, ("ใครได้", "เคยได้", "ประวัติ", "กี่ครั้ง", "บัลลงดอร์", "ใครยิง", "trivia", "history")):
        return "trivia_history"
    return None


def _rewrite(query: str, intent: str, names: list[str], filters: dict) -> str:
    if not re.search(r"[ก-๙]", query):
        return query
    teams = " ".join(names)
    season = filters.get("season", "")
    matchweek = f"matchweek {filters['matchweek']}" if "matchweek" in filters else ""
    dates = " ".join(str(filters[key]) for key in ("date_from", "date_to") if key in filters)
    if intent == "match_result":
        event = "previous match result" if "ก่อนหน้า" in query else "latest match result"
        return " ".join(part for part in (teams, event, season, matchweek, dates) if part)
    if intent == "fixture_schedule":
        return " ".join(part for part in (teams, "next Premier League fixture date opponent", season, matchweek, dates) if part)
    if intent == "standings_stats":
        topic = "top scorer" if "ดาวซัลโว" in query else "standings points ranking"
        return " ".join(part for part in (teams, "Premier League", topic, season, matchweek) if part)
    if intent == "weekly_summary":
        return " ".join(part for part in (teams, "Premier League weekly report summary", season, matchweek, dates) if part)
    if "บัลลงดอร์" in query:
        years = " ".join(re.findall(r"(?:19|20)\d{2}", query))
        return " ".join(part for part in ("Ballon d'Or winner", years) if part)
    if "แชมป์" in query:
        return " ".join(part for part in (teams, "Premier League title championship history count") if part)
    years = " ".join(re.findall(r"(?:19|20)\d{2}", query))
    return " ".join(part for part in (teams, "football trivia history", years) if part)


def enrich(decision: Decision, query: str, context: dict, history: list[dict], teams: TeamDirectory,
           favorite_team_id: int | None = None) -> Decision:
    found = teams.find(query)
    if not found and re.search(r"(แล้ว|นัดนั้น|เขา|ทีมไหน)", query):
        for item in reversed(history[-10:]):
            if item.get("role") == "user":
                found = teams.find(item.get("content", ""))
                if found:
                    break
    if not found and favorite_team_id and re.search(r"(ทีมโปรด|ทีมฉัน|ทีมของฉัน)", query):
        found = [team for team in teams.teams if team.team_id == favorite_team_id]
    decision.team_ids = [team.team_id for team in found]
    if decision.route == "football_rag":
        if decision.team_ids:
            decision.filters["team_ids"] = decision.team_ids
        if context.get("season") and decision.intent != "trivia_history":
            decision.filters["season"] = str(context["season"])
        text = query.lower()
        now = datetime.fromisoformat(context["now"]) if context.get("now") else datetime.now().astimezone()
        if "เมื่อวาน" in text or "yesterday" in text:
            day = (now - timedelta(days=1)).date().isoformat()
            decision.filters.update(date_from=day, date_to=day)
        elif "วันนี้" in text or "today" in text:
            day = now.date().isoformat()
            decision.filters.update(date_from=day, date_to=day)
        elif "สัปดาห์นี้" in text or "this week" in text:
            monday = (now - timedelta(days=now.weekday())).date()
            decision.filters.update(date_from=monday.isoformat(), date_to=(monday + timedelta(days=6)).isoformat())
        match = re.search(r"(?:นัดที่|matchweek\s*)(\d{1,2})", text)
        if match:
            decision.filters["matchweek"] = int(match.group(1))
        elif decision.intent == "weekly_summary" and context.get("current_matchweek") and "สัปดาห์นี้" not in text:
            decision.filters["matchweek"] = int(context["current_matchweek"])
        decision.rewritten_query = _rewrite(query, decision.intent,
                                            [team.short_name for team in found], decision.filters)
    return decision


def decide(query: str, context: dict, history: list[dict], teams: TeamDirectory,
           favorite_team_id: int | None = None) -> Decision | None:
    text = query.lower().strip()
    if not text:
        return Decision("clarify", None, "guard", 1.0, "ไม่มีคำถาม")
    found = teams.find(query)
    if not found and ("ยูไนเต็ด" in text or re.search(r"(?<![A-Za-z])united(?![A-Za-z])", text)):
        return Decision("clarify", None, "guard", 1.0, "ชื่อ United กำกวม")
    if not found and _has(text, ("นัดนั้น", "ทีมไหนชนะ", "เขายิง")) and not history:
        return Decision("clarify", None, "guard", 1.0, "ขาดทีมที่อ้างถึง")
    if len(found) > 2:
        return Decision("clarify", None, "guard", 1.0, "พบหลายทีมในคำถาม")
    intent = _intent(query)
    if intent is None and history and re.search(r"(แล้ว|นัดก่อน|นัดนั้น)", text):
        intent = _intent(" ".join(item.get("content", "") for item in reversed(history[-10:]) if item.get("role") == "user"))
    if intent is None:
        return None
    route, category = INTENT_MAP[intent]
    decision = Decision(route, intent, "guard" if route == "decline" else "rules", 1.0 if route == "decline" else 0.9,
                        f"ตรวจพบ intent {intent}", {"category": [category]} if category else {})
    return enrich(decision, query, context, history, teams, favorite_team_id)
