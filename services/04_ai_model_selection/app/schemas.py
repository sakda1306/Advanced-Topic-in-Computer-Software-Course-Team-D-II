from typing import Literal, Optional
from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class GeneralRequest(BaseModel):
    """Body ของ POST /general — ตรงกับ CONTRACT.md §3 เป๊ะ ห้ามเปลี่ยนชื่อ field"""

    request_id: str
    query: str
    history: list[HistoryMessage] = Field(default_factory=list)
    language: Literal["th", "en"] = "th"


class ClassifyRequest(BaseModel):
    """Body ของ POST /local/classify — CONTRACT.md §3"""

    request_id: str
    text: str


class PredictRequest(BaseModel):
    """Body ของ POST /local/predict (Could) — CONTRACT.md §3"""

    request_id: str
    home_team_id: int
    away_team_id: int
    season: str


class TokenUsage(BaseModel):
    input: int
    output: int


class EngineResult(BaseModel):
    """Response ร่วมของ /general, /local/classify, /local/predict — CONTRACT.md §3"""

    engine: Literal["general_ai", "local_ai"]
    content: str
    data: Optional[dict] = None
    sources: list = Field(default_factory=list)
    model: str
    latency_ms: int
    token_usage: TokenUsage


class ProblemDetail(BaseModel):
    """Error shape ร่วมทุก service — CONTRACT.md §0 (Problem-JSON)"""

    type: str
    title: str
    status: int
    code: str
    detail: str
    service: str = "engines"
    request_id: str
