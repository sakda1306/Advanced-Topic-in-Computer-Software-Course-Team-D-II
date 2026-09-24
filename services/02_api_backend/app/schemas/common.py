"""Shared objects from CONTRACT.md: Source, TokenUsage, Trace, HistoryMessage."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Route = Literal["football_rag", "general_ai", "local_ai", "clarify", "decline"]
Category = Literal["trivia", "match_report", "standings", "fixtures", "weekly_report"]
Origin = Literal["kb", "football-data.org", "api-football", "generated"]
Layer = Literal["guard", "rules", "classifier", "llm"]
Fallback = Literal["retrieval_empty", "retrieval_down", "llm_fallback_provider"]


class PassThrough(BaseModel):
    """Objects produced by other services: unknown fields are kept, not dropped."""

    model_config = ConfigDict(extra="allow")


class Source(PassThrough):
    ref: int
    doc_id: str
    title: str = ""
    category: str | None = None
    origin: str | None = None
    season: str | None = None
    matchweek: int | None = None
    team_ids: list[int] = Field(default_factory=list)
    fetched_at: str | None = None
    url: str | None = None


class TokenUsage(PassThrough):
    input: int = 0
    output: int = 0


class TraceStep(PassThrough):
    name: str
    ms: int | float = 0


class Trace(PassThrough):
    decided_at_layer: str | None = None
    intent: str | None = None
    rewritten_query: str | None = None
    filters: dict[str, object] | None = None
    fallback: str | None = None
    steps: list[TraceStep] = Field(default_factory=list)


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Ok(BaseModel):
    ok: bool = True


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
