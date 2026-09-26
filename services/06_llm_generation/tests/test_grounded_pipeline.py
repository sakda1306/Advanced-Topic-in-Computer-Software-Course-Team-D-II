"""เทส pipeline grounded โดยตรง (ไม่ผ่าน HTTP) ด้วย FakeLLM ที่กำหนดคำตอบเองได้

ครอบคลุมกรณี P2 ใน PR review: chunk เดียวมีหลายแมตช์ (สัปดาห์จาก 07/05) แล้ว
คำตอบอ้างสกอร์ของคู่ที่สอง ต้องไม่ถูก numeric_guard ปฏิเสธเป็น insufficient
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.client import LLMResult, TokenUsage
from app.pipeline.grounded import run_grounded
from app.schemas import Context, GenerateRequest, HistoryMessage, Source


class _FakeLLM:
    """คืนคำตอบที่กำหนดไว้ล่วงหน้า ไม่สนใจ prompt ที่ส่งเข้ามา"""

    def __init__(self, text: str):
        self._text = text
        self.calls = 0

    async def chat(self, messages, *, temperature, max_tokens, deadline, purpose):
        self.calls += 1
        return LLMResult(
            text=self._text,
            model="fake/llm",
            provider="fake",
            usage=TokenUsage(input=10, output=10),
            fallback_used=False,
            latency_ms=1,
        )


def _multi_match_context() -> Context:
    text = (
        "Arsenal beat Chelsea 2-1 at the Emirates on matchweek 5. "
        "Later that day, Liverpool beat Everton 3-0 at Anfield."
    )
    return Context(
        ref=1,
        text=text,
        source=Source(
            ref=1,
            doc_id="weekly-2026-mw05",
            title="Premier League 2026/27 · Matchweek 5",
            category="weekly_report",
            origin="football-data.org",
            season="2026",
            matchweek=5,
            team_ids=[57, 61, 40, 1044],
            fetched_at="2026-09-21T09:00:00+07:00",
            url=None,
        ),
    )


@pytest.mark.asyncio
async def test_second_match_score_in_shared_chunk_not_rejected():
    """คำตอบที่อ้างสกอร์ของคู่ที่สองในก้อนเดียวกันต้องผ่าน numeric guard"""
    req = GenerateRequest(
        request_id="77777777-7777-7777-7777-777777777777",
        mode="grounded",
        query="ลิเวอร์พูลเจออีฟเวอร์ตันผลเป็นยังไง",
        language="th",
        contexts=[_multi_match_context()],
        history=[],
    )
    fake_llm = _FakeLLM("ลิเวอร์พูลชนะเอฟเวอร์ตัน 3-0 [1]")
    settings = Settings(llm_mock=True, numeric_guard="strict")

    resp = await run_grounded(req, llm=fake_llm, settings=settings, request_id=req.request_id)

    assert "ไม่พบข้อมูลที่เพียงพอ" not in resp.answer
    assert "3-0" in resp.answer
    assert fake_llm.calls == 1  # ไม่ต้อง retry เพราะสกอร์ตรงกับ context อยู่แล้ว
    assert resp.sources and resp.sources[0].ref == 1


@pytest.mark.asyncio
async def test_first_match_score_in_shared_chunk_still_detected():
    """ของเดิม (คู่แรก) ก็ยังต้องตรวจผ่านตามปกติ กันการแก้ไขทำให้คู่แรกพัง"""
    req = GenerateRequest(
        request_id="88888888-8888-8888-8888-888888888888",
        mode="grounded",
        query="อาร์เซนอลเจอเชลซีผลเป็นยังไง",
        language="th",
        contexts=[_multi_match_context()],
        history=[],
    )
    fake_llm = _FakeLLM("อาร์เซนอลชนะเชลซี 2-1 [1]")
    settings = Settings(llm_mock=True, numeric_guard="strict")

    resp = await run_grounded(req, llm=fake_llm, settings=settings, request_id=req.request_id)

    assert "ไม่พบข้อมูลที่เพียงพอ" not in resp.answer
    assert "2-1" in resp.answer
    assert fake_llm.calls == 1
