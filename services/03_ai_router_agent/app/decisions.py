import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .chat import chat_enabled, chat_kind
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
    "player_info": ("football_rag", "player"),
    "chitchat": ("chat", None),
}

# CONTRACT v1.5: the 04 classifier does not know player_info, so these rules are its main entry.
PLAYER_WORDS = ("นักเตะ", "ผู้เล่น", "สควอด", "ผู้รักษาประตู", "กองหน้า", "กองกลาง", "กองหลัง",
                "โค้ช", "ผู้จัดการทีม", "กุนซือ", "ตำแหน่งอะไร", "เล่นตำแหน่ง", "อายุเท่า", "สัญชาติ",
                "squad", "players", "who plays for", "head coach", "manager of", "coach of",
                "how old is", "nationality")
# Goal and table questions stay with the scorer/standings rules or fall through to the LLM.
NOT_PLAYER_WORDS = ("ยิง", "ทำประตู", "กี่ประตู", "กี่ลูก", "ตาราง", "goals", "scored", "assist",
                    "table")

MATCHWEEK_PATTERN = re.compile(r"(?:นัดที่\s*|แมตช์วีค\s*|สัปดาห์ที่\s*|matchweek\s*)(\d+)")
OTHER_COMPETITIONS = ("ลาลีกา", "แชมเปียนส์ลีก", "แชมเปี้ยนส์ลีก", "ยูฟ่า",
                      "บุนเดสลีกา", "กัลโช่", "ฟุตบอลโลก", "la liga",
                      "champions league", "serie a", "bundesliga", "ligue 1", "world cup")
# Whole-season outlook questions (CONTRACT v1.7): answered from 07 /football/simulation.
SEASON_PREDICTION = re.compile(
    r"จะ\s*(?:ได้|เป็น|คว้า)?\s*แชมป์|จะ\s*ตกชั้น|จะ\s*(?:ติด|จบ)\s*(?:ท็อป|อันดับ)|เสี่ยง\s*ตกชั้น"
    r"|(?:มี\s*)?โอกาส\s*(?:ได้\s*)?(?:แชมป์|ติดท็อป|ท็อป|ตกชั้น|จบอันดับ)"
    r"|\bwho will (?:win the (?:premier league|league|title)|be relegated|finish)\b"
    r"|\bchances? of (?:winning the (?:league|title)|(?:a )?top[- ]?(?:4|four)|relegation|being relegated)\b")
# Short follow-ups about one match ("เขายิงกี่ลูก", "who scored?") and the next one ("who do they play next?").
MATCH_GOAL_WORDS = ("ยิงกี่ลูก", "ยิงกี่ประตู", "ได้กี่ประตู", "ยิงได้กี่", "ใครทำประตู", "ใครยิง")
MATCH_RESULT_EN = re.compile(r"\bwho (?:scored|won)\b|\bdid \w+(?: \w+)? win\b|\bhow did \w+(?: \w+)? do\b")
NEXT_MATCH_EN = re.compile(r"\bnext (?:match|game|opponent)\b|\bplay next\b")
RECORD_WORDS_TH = ("มากที่สุด", "เร็วที่สุด", "สถิติ", "ตลอดกาล", "ตลอดมา", "ประวัติศาสตร์", "นัดชิง",
                   "คนแรก", "ทีมแรก", "ครั้งแรก", "ก่อนคนอื่น")
RECORD_WORDS_EN = re.compile(r"\b(?:league|title|trophy|cup|ever|record|fastest|ballon|award)\b")
# Competitions outside the Premier League. Their questions are history, and the trivia documents
# name them in English, so the search text carries the English name instead of "Premier League".
COMPETITION_TERMS = (
    ("ฟุตบอลโลก", "FIFA World Cup"), ("บอลโลก", "FIFA World Cup"), ("เวิลด์คัพ", "FIFA World Cup"),
    ("แชมเปียนส์ลีก", "UEFA Champions League European Cup"),
    ("แชมเปี้ยนส์ลีก", "UEFA Champions League European Cup"),
    ("ถ้วยยุโรป", "UEFA Champions League European Cup"),
    ("แชมป์ยุโรป", "UEFA European Championship Euro UEFA Champions League European Cup"),
    ("ยูโร", "UEFA European Championship Euro"), ("คอนเฟด", "FIFA Confederations Cup"),
    ("โคปา", "Copa America"), ("โอลิมปิก", "Olympic Games football"),
)
INTERNATIONAL_WORDS = (*(thai for thai, _ in COMPETITION_TERMS), "ทีมชาติ", "world cup", "euro",
                       "champions league", "copa america", "olympic", "national team", "confederations")
SEASON_WORDS = ("แชมป์", "ท็อปโฟร์", "ท็อป 4", "ท็อป4", "top 4", "top four", "ตกชั้น", "relegat",
                "อันดับ", "title", "finish")
# v1.11: 07's Premier League archive (past seasons and head-to-head) lives in its own category.
HISTORICAL = "historical"
HEAD_TO_HEAD_WORDS = ("เคยชนะ", "เคยเจอ", "ชนะกี่นัด", "สถิติพบกัน", "สถิติเจอกัน", "ประวัติการพบกัน",
                      "head to head", "head-to-head", "h2h")
# "เจอกันกี่ครั้ง" counts meetings; "เจอกันกี่โมง" / "ชนะกันกี่ลูก" are about one match.
HEAD_TO_HEAD_COUNT = re.compile(r"(?:เจอกัน|ชนะกัน|พบกัน)\s*กี่\s*(?:นัด|ครั้ง|หน)")
# The archive ends last season: questions about this season or one match stay with live data.
CURRENT_WORDS = ("เมื่อวาน", "วันนี้", "คืนนี้", "พรุ่งนี้", "นัดล่าสุด", "นัดก่อน", "นัดหน้า", "นัดต่อไป",
                 "ฤดูกาลนี้", "ซีซั่นนี้", "ปีนี้", "กี่โมง", "กี่ทุ่ม", "this season", "yesterday", "today",
                 "last match", "next match")
# Without a known club, a season question must name the league to be about the Premier League.
PL_WORDS = ("พรีเมียร์ลีก", "premier league", "ลีกอังกฤษ", "epl", "พรีเมียร์ชิพ")
# Former Premier League clubs the team directory does not know (no team_id in 07's archive),
# with the English name the archive documents use.
ARCHIVE_CLUBS = {
    "แบล็คเบิร์น": "Blackburn Rovers", "blackburn": "Blackburn Rovers",
    "โบลตัน": "Bolton Wanderers", "bolton": "Bolton Wanderers",
    "เลสเตอร์": "Leicester City", "leicester": "Leicester City",
    "เวสต์แฮม": "West Ham United", "west ham": "West Ham United",
    "วูล์ฟส์": "Wolverhampton Wanderers", "wolves": "Wolverhampton Wanderers",
    "เบิร์นลีย์": "Burnley", "burnley": "Burnley",
    "เซาธ์แฮมป์ตัน": "Southampton", "southampton": "Southampton",
    "มิดเดิลสโบรช์": "Middlesbrough", "middlesbrough": "Middlesbrough",
    "วัตฟอร์ด": "Watford", "watford": "Watford",
    "นอริช": "Norwich City", "norwich": "Norwich City",
    "สโต๊ค": "Stoke City", "stoke": "Stoke City",
    "สวอนซี": "Swansea City", "swansea": "Swansea City",
    "วีแกน": "Wigan Athletic", "wigan": "Wigan Athletic",
    "พอร์ทสมัธ": "Portsmouth", "portsmouth": "Portsmouth",
    "เรดดิ้ง": "Reading", "reading": "Reading",
    "ดาร์บี้": "Derby County", "derby": "Derby County",
    "เบอร์มิงแฮม": "Birmingham City", "birmingham": "Birmingham City",
    "แบล็คพูล": "Blackpool", "blackpool": "Blackpool",
    "แบรดฟอร์ด": "Bradford City", "bradford": "Bradford City",
    "คาร์ดิฟฟ์": "Cardiff City", "cardiff": "Cardiff City",
    "ชาร์ลตัน": "Charlton Athletic", "charlton": "Charlton Athletic",
    "ฮัดเดอร์สฟิลด์": "Huddersfield Town", "huddersfield": "Huddersfield Town",
    "ลูตัน": "Luton Town", "luton": "Luton Town",
    "โอลด์แฮม": "Oldham Athletic", "oldham": "Oldham Athletic",
    "คิวพีอาร์": "Queens Park Rangers", "qpr": "Queens Park Rangers",
    "เชฟฟิลด์": "Sheffield", "sheffield": "Sheffield",
    "สวินดอน": "Swindon Town", "swindon": "Swindon Town",
    "เวสต์บรอม": "West Bromwich Albion", "west brom": "West Bromwich Albion",
    "วิมเบิลดัน": "Wimbledon", "wimbledon": "Wimbledon",
    "บาร์นสลีย์": "Barnsley", "barnsley": "Barnsley",
}
ARCHIVE_CLUB_WORDS = tuple(ARCHIVE_CLUBS)
HISTORY_SEASON_WORDS = ("แชมป์", "อันดับ", "ตาราง", "ตกชั้น", "แต้ม", "คะแนน", "ผลงาน", "ชนะกี่", "แพ้กี่",
                        "เสมอกี่", "ยิงได้กี่", "ดาวซัลโว", "champion", "title", "table", "relegat", "finish",
                        "points", "who won", "winner")
# Cups are not in the league archive: a league champion must not answer a cup question.
CUP_WORDS = ("เอฟเอคัพ", "fa cup", "ลีกคัพ", "league cup", "คาราบาว", "carabao", "คอมมูนิตี้ชิลด์",
             "community shield", "บัลลงดอร์", "ballon", "คัพ", " cup", "ถ้วย", "efl", "ซีเกมส์", "sea games",
             "เอเชียน", "asian", "ไทยลีก", "thai league", "ดิวิชั่น", "division")


def normalize_thai(text: str) -> str:
    """Users often type two sara e (เเ) where they mean sara ae (แ)."""
    return text.replace("เเ", "แ")


def season_prediction(query: str) -> bool:
    return bool(SEASON_PREDICTION.search(query.lower()))


def prediction_kind(query: str, team_ids: list[int]) -> str:
    """season = title / top 4 / relegation outlook · match = two teams · otherwise ask."""
    text = query.lower()
    if season_prediction(text):
        return "season"
    if len(team_ids) >= 2:
        return "match"
    if _has(text, SEASON_WORDS):
        return "season"
    return "needs_team"


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
    kind: str | None = None  # route `chat` only: the kind of chit-chat (also in `reasoning`)


def _category_filter(intent: str) -> dict:
    if intent == "trivia_history":
        return {"category": ["trivia", HISTORICAL]}
    category = INTENT_MAP[intent][1]
    return {"category": [category]} if category else {}


def classify_intent(label: str, score: float) -> Decision | None:
    if label == "chitchat" and not chat_enabled():
        label = "out_of_scope"
    if label not in INTENT_MAP or score < 0.75:
        return None
    return Decision(INTENT_MAP[label][0], label, "classifier", score, f"classifier: {label}",
                    _category_filter(label))


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


def _has_historical_marker(text: str) -> bool:
    if _has(text, ("ตลอดกาล", "ตลอดมา", "ประวัติศาสตร์", "ย้อนหลัง", "ฤดูกาลที่แล้ว",
                   "ซีซั่นที่แล้ว", "ปีที่แล้ว", "ฤดูกาลก่อน", "ซีซั่นก่อน")):
        return True
    return bool(re.search(r"\b(?:all[- ]time|ever|in history|last season|previous season)\b", text))


def _record_question(text: str, current_season: str | None = None) -> bool:
    if (_has_historical_marker(text) or _has(text, RECORD_WORDS_TH) or RECORD_WORDS_EN.search(text)
            or _has(text, INTERNATIONAL_WORDS)):
        return True
    # A year outside the current season ("นัดชิงปี 2005") points at history, not at the latest match.
    season = str(current_season or "")
    allowed = {season, str(int(season) + 1)} if season.isdigit() else set()
    return any(year not in allowed for year in re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text))


def _previous_season(text: str) -> bool:
    return _has(text, ("ฤดูกาลที่แล้ว", "ซีซั่นที่แล้ว", "ปีที่แล้ว", "ฤดูกาลก่อน", "ซีซั่นก่อน")) or bool(
        re.search(r"\b(?:last season|previous season)\b", text)
    )


def _top_scorer_question(text: str) -> bool:
    text = text.replace("ลีกสูงสุด", "")  # "top-flight league", not "most goals"
    return _has(text, ("ดาวซัลโว", "top scorer", "leading scorer", "golden boot")) or (
        _has(text, ("ยิง", "ทำประตู", "goals", "scored"))
        and _has(text, ("เยอะสุด", "เยอะที่สุด", "มากที่สุด", "สูงสุด", "most goals", "top scorer", "leading scorer"))
    )


def _season_in(text: str, current_season: str | None) -> tuple[str, bool] | None:
    """Read explicit season years; a bare year means its starting season."""
    full = re.search(r"(?<!\d)((?:19|20)\d{2})\s*[/\-]\s*((?:19|20)\d{2}|\d{2})(?!\d)", text)
    short = re.search(r"(?<!\d)(\d{2})\s*[/\-]\s*(\d{2})(?!\d)", text) if not full else None
    if full or short:
        match = full or short
        start = int(match.group(1)) if full else 2000 + int(match.group(1))
        if short and int(match.group(1)) >= 50:  # "98/99" is 1998/99; "27/28" stays 2027/28
            start -= 100
        end = int(match.group(2))
        if end != start + 1 and end != (start + 1) % 100:
            return None
        assumed = False
    else:
        years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
        if len(years) == 1:
            start = int(years[0])
            assumed = True
        elif not years and _previous_season(text) and str(current_season or "").isdigit():
            start = int(current_season) - 1
            assumed = False
        else:
            return None
    if str(start) == str(current_season):
        return None
    return str(start), assumed


def historical_scorer_season(query: str, current_season: str | None) -> tuple[str, bool] | None:
    """Read explicit season years; a bare year means its starting season."""
    text = query.lower()
    if not _top_scorer_question(text) or _has(text, ("ตลอดกาล", "ประวัติศาสตร์")) or re.search(
        r"\b(?:all[- ]time|ever|in history)\b", text
    ):
        return None
    return _season_in(text, current_season)


def _head_to_head(text: str) -> bool:
    return _has(text, HEAD_TO_HEAD_WORDS) or bool(HEAD_TO_HEAD_COUNT.search(text))


def _season_label(start: int) -> str:
    return f"{start}/{str(start + 1)[2:]}"


def history_filters(query: str, team_count: int, current_season: str | None) -> dict | None:
    """Questions the 07 Premier League archive answers (CONTRACT v1.11)."""
    text = query.lower()
    if _has(text, (*OTHER_COMPETITIONS, *INTERNATIONAL_WORDS, *CUP_WORDS)):
        return None
    if team_count == 2 and _head_to_head(text) and not _has(text, CURRENT_WORDS):
        return {"category": [HISTORICAL]}
    if not str(current_season or "").isdigit() or not _has(text, HISTORY_SEASON_WORDS):
        return None
    if team_count == 0 and not _has(text, (*PL_WORDS, *ARCHIVE_CLUB_WORDS)):
        return None
    season = _season_in(text, current_season)
    # Before 1992/93 the archive has nothing; trivia may still know (old First Division).
    if season is None or not 1992 <= int(season[0]) < int(current_season):
        return None
    start, assumed = season
    # A bare year may mean the season that starts or ends in it: search both, do not filter.
    return {"category": [HISTORICAL]} if assumed else {"category": [HISTORICAL], "season": start}


def league_wide_scorer_query(query: str, teams: TeamDirectory) -> bool:
    """Limit the verified winner shortcut to league player rankings."""
    text = query.lower()
    if teams.find(query) or MATCHWEEK_PATTERN.search(text) or _has(text, OTHER_COMPETITIONS):
        return False
    if _has(text, ("ทีมไหน", "สโมสรไหน", "which team", "which club", "team with most",
                   "เสียประตู", "conceded", "goals against", "ผู้รักษาประตู", "goalkeeper",
                   "เกมไหน", "นัดไหน", "ในเกม", "ในแมตช์", "which match", "which game",
                   "per match", "against",
                   "รอง", "runner-up", "second place", "อันดับสอง", "อันดับ 2",
                   "ตั้งแต่", "since", "จนถึง", "ถึง", "เดือน", "มกราคม", "กุมภาพันธ์",
                   "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม",
                   "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")):
        return False
    if re.search(r"\bsecond\b", text) or re.search(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
                 r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
                 r"dec(?:ember)?)\b", text):
        return False
    return _has(text, ("ใคร", "ดาวซัลโว", "top scorer", "leading scorer", "golden boot")) or bool(
        re.search(r"\bwho\b", text)
    )


def _current_top_scorer(text: str, current_season: str | None = None) -> bool:
    if not _top_scorer_question(text) or _has_historical_marker(text) or _has(text, INTERNATIONAL_WORDS):
        return False
    if historical_scorer_season(text, current_season):
        return False
    years = re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if not years:
        return True
    if not str(current_season or "").isdigit():
        return False
    if all(year == str(current_season) for year in years):
        return True
    next_year = str(int(current_season) + 1)
    return years == [str(current_season), next_year] and bool(re.search(
        rf"(?<!\d){re.escape(str(current_season))}\s*[/\-]\s*{re.escape(next_year)}(?!\d)", text
    ))


def _intent(query: str, current_season: str | None = None) -> str | None:
    text = query.lower()
    if _has(text, OTHER_COMPETITIONS) and _top_scorer_question(text):
        return "out_of_scope"
    if _has(text, ("พนัน", "เดิมพัน", "ราคาบอล", "ทีเด็ด", "แทงบอล", "odds", "betting", "bet ")):
        return "out_of_scope"
    if _has(text, ("อากาศ", "ร้านอาหาร", "bitcoin", "โค้ด python", "เขียนเว็บ", "หุ้น")):
        return "out_of_scope"
    if _has(text, ("ทำนาย", "คาดการณ์", "พยากรณ์ผล", "predict", "who will win", "โอกาสชนะ", "จะชนะ")) or (
            season_prediction(text)):
        return "prediction"
    if _has(text, ("ใบเหลือง", "ใบแดง", "ลูกโทษ")) and _has(
            text, ("เมื่อวาน", "เมื่อคืน", "นัดล่าสุด", "นัดก่อน", "นัดที่", "แมตช์", "เกมล่าสุด", "ผลแข่ง")):
        return "match_result"
    if _has(text, ("กฎ", "ล้ำหน้า", "var ", "ใบเหลือง", "ใบแดง", "แฮนด์บอล", "ลูกโทษ", "แผนการเล่น", "free kick", "ผู้รักษาประตูใช้มือ")):
        return "general_football"
    if _has(text, ("สรุป", "ไฮไลต์", "weekly summary")) and _has(text, ("สัปดาห์", "นัด", "week", "พรีเมียร์ลีก")):
        return "weekly_summary"
    if _has(text, ("แชมป์", "บัลลงดอร์", "ประวัติ", "trivia", "history")):
        return "trivia_history"
    if _has(text, ("โปรแกรม", "เตะกับใครต่อ", "แข่งกับใครต่อ", "นัดหน้า", "เมื่อไร", "วันไหน", "fixture", "schedule",
                   "นัดต่อไป", "นัดถัดไป", "เจอใครต่อ", "เจอกับใครต่อ")) or NEXT_MATCH_EN.search(text):
        return "fixture_schedule"
    if _top_scorer_question(text):
        return "standings_stats" if _current_top_scorer(text, current_season) else "trivia_history"
    if re.search(r"\bscorers?\b", text):
        return "trivia_history" if _has_historical_marker(text) else "standings_stats"
    if _has(text, ("ตารางคะแนน", "จ่าฝูง", "อันดับ", "กี่แต้ม", "standings", "points", "top of the table",
                   "league table")):
        return "standings_stats"
    if (_has(text, PLAYER_WORDS) or re.search(r"\bposition\b.*\bplay", text)) and not _has(
            text, NOT_PLAYER_WORDS):
        return "player_info"
    if _has(text, MATCH_GOAL_WORDS) or MATCH_RESULT_EN.search(text):
        # "Who scored the fastest goal ever" asks for a record, not for one match.
        return "trivia_history" if _record_question(text, current_season) else "match_result"
    if _has(text, ("เมื่อวาน", "นัดล่าสุด", "นัดก่อน", "ชนะไหม", "ผลนัด", "ผลแข่ง", "จบเท่าไร", "สกอร์", "result")) or re.search(r"\bscore\b", text):
        return "match_result"
    if _has(text, ("ใครได้", "เคยได้", "ประวัติ", "กี่ครั้ง", "บัลลงดอร์", "ใครยิง", "trivia", "history")):
        return "trivia_history"
    if _has(text, INTERNATIONAL_WORDS):
        return "trivia_history"
    return None


def _competition_names(query: str) -> str:
    names = [english for thai, english in COMPETITION_TERMS if thai in query]
    return " ".join(dict.fromkeys(" ".join(names).split()))


def _rewrite(query: str, intent: str, names: list[str], filters: dict) -> str:
    if not re.search(r"[ก-๙]", query):
        return query
    def keep_question(*parts: str) -> str:
        return " ".join(part for part in (*parts, query.strip()) if part)

    teams = " ".join(names)
    if filters.get("category") == [HISTORICAL]:
        start = filters.get("season")
        # Archive documents name clubs in English; add the ones the team directory cannot.
        lowered = query.lower()
        former = [name for word, name in ARCHIVE_CLUBS.items() if word in lowered and name not in teams]
        teams = " ".join(dict.fromkeys([*names, *former]))
        if start is not None:
            return keep_question(teams, "Premier League", _season_label(int(start)), "final table standings")
        year = None if _head_to_head(query.lower()) else re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", query)
        if year is None:
            return keep_question(teams, "Premier League head-to-head record")
        end = int(year.group(1))
        return keep_question(teams, "Premier League", _season_label(end - 1), _season_label(end),
                             "final table standings")
    season = filters.get("season", "")
    matchweek = f"matchweek {filters['matchweek']}" if "matchweek" in filters else ""
    dates = " ".join(str(filters[key]) for key in ("date_from", "date_to") if key in filters)
    if intent == "match_result":
        event = "previous match result" if "ก่อนหน้า" in query else "latest match result"
        return keep_question(teams, event, season, matchweek, dates)
    if intent == "fixture_schedule":
        return keep_question(teams, "next Premier League fixture date opponent", season, matchweek, dates)
    if intent == "standings_stats":
        topic = "top scorer" if _top_scorer_question(query.lower()) else "standings points ranking"
        return keep_question(teams, "Premier League", topic, season, matchweek)
    if intent == "weekly_summary":
        return keep_question(teams, "Premier League weekly report summary", season, matchweek, dates)
    if intent == "player_info":
        return keep_question(teams, "Premier League squad players position nationality coach", season)
    years = " ".join(re.findall(r"(?:19|20)\d{2}", query))
    if "บัลลงดอร์" in query:
        return keep_question("Ballon d'Or winner", years)
    competitions = _competition_names(query)
    if competitions:
        return keep_question(teams, competitions, years)
    # A title question about a named Premier League team; without a team the Thai text already
    # names the league and an English prefix only pulled other documents up (Thai golden set).
    if "แชมป์" in query and teams:
        return keep_question(teams, "Premier League title", "count" if "กี่ครั้ง" in query else "")
    # No generic English prefix: it pulled the same unrelated trivia to the top (Thai golden set).
    return keep_question(teams, years)


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
        if decision.intent == "trivia_history":
            decision.rewritten_query = _rewrite(query, decision.intent,
                                                [team.short_name for team in found], decision.filters)
            return decision
        if decision.team_ids:
            decision.filters["team_ids"] = decision.team_ids
        if context.get("season"):
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
        match = MATCHWEEK_PATTERN.search(text)
        if match:
            decision.filters["matchweek"] = int(match.group(1))
        elif decision.intent in ("weekly_summary", "standings_stats") and context.get("current_matchweek") and "สัปดาห์นี้" not in text:
            decision.filters["matchweek"] = int(context["current_matchweek"])
        decision.rewritten_query = _rewrite(query, decision.intent,
                                            [team.short_name for team in found], decision.filters)
    return decision


def decide(query: str, context: dict, history: list[dict], teams: TeamDirectory,
           favorite_team_id: int | None = None) -> Decision | None:
    text = query.lower().strip()
    if not text:
        return Decision("clarify", None, "guard", 1.0, "ไม่มีคำถาม")
    matchweek = MATCHWEEK_PATTERN.search(text)
    if matchweek and not 1 <= int(matchweek.group(1)) <= 38:
        return Decision("clarify", None, "guard", 1.0, "เลขนัดต้องอยู่ระหว่าง 1 ถึง 38")
    found = teams.find(query)
    if not found and ("ยูไนเต็ด" in text or re.search(r"(?<![A-Za-z])united(?![A-Za-z])", text)):
        return Decision("clarify", None, "guard", 1.0, "ชื่อ United กำกวม")
    if not found and _has(text, ("นัดนั้น", "ทีมไหนชนะ", "เขายิง")) and not history:
        return Decision("clarify", None, "guard", 1.0, "ขาดทีมที่อ้างถึง")
    if len(found) > 2:
        return Decision("clarify", None, "guard", 1.0, "พบหลายทีมในคำถาม")
    intent = _intent(query, context.get("season"))
    if intent is None and chat_enabled():
        kind = chat_kind(normalize_thai(text), len(found))
        if kind:
            return Decision("chat", "chitchat", "rules", 0.9, f"คุยทั่วไป: {kind}", kind=kind)
    if intent is None and history and re.search(r"(แล้ว|นัดก่อน|นัดนั้น)", text):
        for item in reversed(history[-10:]):
            if item.get("role") == "user":
                intent = _intent(item.get("content", ""), context.get("season"))
                if intent is not None:
                    break
    if intent not in ("out_of_scope", "prediction"):
        past = history_filters(query, len(found), context.get("season"))
        if past is not None:
            decision = Decision("football_rag", "trivia_history", "rules", 0.9,
                                "คำถามสถิติย้อนหลังพรีเมียร์ลีก", past)
            return enrich(decision, query, context, history, teams, favorite_team_id)
    if intent is None:
        return None
    route = INTENT_MAP[intent][0]
    decision = Decision(route, intent, "guard" if route == "decline" else "rules", 1.0 if route == "decline" else 0.9,
                        f"ตรวจพบ intent {intent}", _category_filter(intent))
    return enrich(decision, query, context, history, teams, favorite_team_id)
