import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .llm_client import LLMUnavailableError, call_general_ai
from .local_classifier import ModelNotLoadedError, classify as classify_intent, model_version
from .schemas import (
    ClassifyRequest,
    EngineResult,
    GeneralRequest,
    PredictRequest,
    ProblemDetail,
    TokenUsage,
)
from .token_budget import trim_history_to_budget

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("engines")

app = FastAPI(title="engines (04_ai_engines)")

SYSTEM_PROMPT_TH = (
    "คุณเป็นผู้ช่วยตอบคำถามเกี่ยวกับฟุตบอล Premier League "
    "ตอบให้กระชับ ถูกต้อง เป็นกันเอง และตอบเป็นภาษาไทย "
    "ถ้าคำถามต้องการข้อมูลสด เช่น ผลการแข่งขันล่าสุด ตารางคะแนน หรือโปรแกรมการแข่งขัน "
    "ให้บอกตรง ๆ ว่าคุณไม่มีข้อมูลสดในส่วนนี้ อย่าเดาผลหรือสกอร์เด็ดขาด"
)
SYSTEM_PROMPT_EN = (
    "You are an assistant that answers questions about the Premier League. "
    "Answer concisely, accurately, and in English. "
    "If the question needs live data such as recent results, standings, or fixtures, "
    "say plainly that you don't have live data for that — never guess a score or result."
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """CONTRACT.md §0: ถ้าไม่มี X-Request-ID ให้สร้าง UUID แล้วส่งต่อ/ใส่ log ทุกครั้ง"""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    t0 = time.monotonic()
    response = await call_next(request)
    ms = int((time.monotonic() - t0) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        '{"event":"http_request","path":"%s","status":%d,"ms":%d,"request_id":"%s"}',
        request.url.path,
        response.status_code,
        ms,
        request_id,
    )
    return response


def _problem(*, status: int, code: str, title: str, detail: str, request_id: str) -> JSONResponse:
    body = ProblemDetail(
        type=f"https://errors.football-assistant.local/{code.lower().replace('_', '-')}",
        title=title,
        status=status,
        code=code,
        detail=detail,
        service=settings.SERVICE_NAME,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(),
        media_type="application/problem+json",
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.SERVICE_NAME, "version": settings.VERSION}


@app.post("/general")
def general(body: GeneralRequest, request: Request):
    request_id = body.request_id or getattr(request.state, "request_id", str(uuid.uuid4()))

    system_prompt = SYSTEM_PROMPT_TH if body.language == "th" else SYSTEM_PROMPT_EN

    # D4: ตัด history เก่าสุดออกจนกว่าจะอยู่ในงบ token โดยประมาณ (เก็บข้อความใหม่สุดไว้ก่อน)
    history_dicts = [{"role": h.role, "content": h.content} for h in body.history[-10:]]
    trimmed_history = trim_history_to_budget(
        history_dicts,
        system_prompt=system_prompt,
        query=body.query,
        max_input_tokens=settings.GENERAL_MAX_INPUT_TOKENS,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(trimmed_history)
    messages.append({"role": "user", "content": body.query})

    t0 = time.monotonic()
    try:
        content, model_used, token_usage = call_general_ai(
            messages=messages,
            max_tokens=settings.GENERAL_MAX_TOKENS,
            request_id=request_id,
        )
    except LLMUnavailableError as e:
        return _problem(
            status=503,
            code="LLM_UNAVAILABLE",
            title="LLM providers unavailable",
            detail=f"ทั้ง Groq และ Gemini เรียกไม่สำเร็จ: {e}",
            request_id=request_id,
        )

    latency_ms = int((time.monotonic() - t0) * 1000)
    result = EngineResult(
        engine="general_ai",
        content=content,
        data=None,
        sources=[],
        model=model_used,
        latency_ms=latency_ms,
        token_usage=TokenUsage(**token_usage),
    )
    return result.model_dump()


@app.post("/local/classify")
def local_classify(body: ClassifyRequest, request: Request):
    """D3 — router ใช้เส้นนี้เป็นชั้น classifier ก่อนตัดสินใจ route (CONTRACT.md §3)"""
    request_id = body.request_id or getattr(request.state, "request_id", str(uuid.uuid4()))

    t0 = time.monotonic()
    try:
        result_data = classify_intent(body.text)
        model_used = model_version()
    except ModelNotLoadedError as e:
        return _problem(
            status=503,
            code="MODEL_UNAVAILABLE",
            title="Local classifier model unavailable",
            detail=str(e),
            request_id=request_id,
        )
    latency_ms = int((time.monotonic() - t0) * 1000)

    result = EngineResult(
        engine="local_ai",
        content=f"intent: {result_data['label']} ({result_data['score']:.2f})",
        data=result_data,
        sources=[],
        model=model_used,
        latency_ms=latency_ms,
        token_usage=TokenUsage(input=0, output=0),  # ไม่ได้เรียก LLM
    )
    return result.model_dump()


@app.post("/local/predict")
def local_predict(body: PredictRequest, request: Request):
    """
    D5 (Could) — ทำนายผลนัดด้วย Poisson model จากผลที่ 07 (football-data) เก็บไว้

    ยังตอบ 501 ตามที่ CONTRACT.md §3 อนุญาตไว้ล่วงหน้า เพราะมี 2 อย่างที่ยังไม่พร้อมจริง ๆ
    (ไม่ใช่แค่ "ยังไม่ได้เขียนโค้ด"):

    1. service `07_football_data` ยังไม่ถูกสร้าง (ตาม SCHEDULE.md ทุก service ยังเป็น placeholder)
       จึงไม่มี "ผลที่ 07 เก็บไว้" ให้ดึงจริง
    2. CONTRACT.md §7 (api → football-data) ไม่ได้ให้สิทธิ์ `engines` เรียก football-data โดยตรง —
       คนเรียกที่ระบุไว้มีแค่ `api` และ `router` (เฉพาะ `/football/teams`) เท่านั้น การจะให้ /local/predict
       ดึงผลย้อนหลังมาคำนวณเองต้องแก้ CONTRACT.md เพิ่ม § ใหม่ก่อน (ต้อง approve จาก sakda1306 + เจ้าของ 07)

    ส่วนที่ "ทำแล้วจริง" คือคณิตศาสตร์ Poisson ล้วน ๆ ใน app/poisson.py (มี unit test ครบ
    ใน tests/test_poisson.py) — พร้อมต่อกับข้อมูลจริงทันทีที่มี 07 และ path การเรียกที่ตกลงกันแล้ว
    """
    request_id = body.request_id or getattr(request.state, "request_id", str(uuid.uuid4()))
    return _problem(
        status=501,
        code="NOT_IMPLEMENTED",
        title="Prediction feature not available yet",
        detail=(
            "ฟีเจอร์ทำนายผลยังไม่เปิดใช้งาน — รอ service 07_football_data และการเพิ่ม CONTRACT.md "
            "ให้ engines อ่านผลย้อนหลังได้ก่อน (ดู docstring ของ endpoint นี้ใน main.py)"
        ),
        request_id=request_id,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(
        '{"event":"unhandled_exception","error":"%s","request_id":"%s"}', str(exc), request_id
    )
    return _problem(
        status=500,
        code="INTERNAL_ERROR",
        title="Internal server error",
        detail="เกิดข้อผิดพลาดที่ไม่คาดคิดใน engines",
        request_id=request_id,
    )
