import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .llm_client import LLMUnavailableError, call_general_ai
from .schemas import EngineResult, GeneralRequest, ProblemDetail, TokenUsage

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
    messages = [{"role": "system", "content": system_prompt}]
    for h in body.history[-10:]:  # กันบริบทยาวเกินงบเวลา/โทเค็น
        messages.append({"role": h.role, "content": h.content})
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
