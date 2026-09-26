"""Problem-JSON error handling ตามหัวข้อ 4.1"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

PROBLEM_BASE = "https://errors.football-assistant.local"


class LLMUnavailable(Exception):
    """เมื่อทั้ง provider หลักและสำรองล่ม"""


class AppValidationError(Exception):
    """422 error ที่เกิดจาก business rule (เช่น ref ซ้ำ, draft ว่าง)"""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def _request_id(request: Request) -> str:
    rid = request.headers.get("X-Request-ID")
    if rid:
        return rid
    return str(uuid.uuid4())


def problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or _request_id(request)
    body = {
        "type": f"{PROBLEM_BASE}/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "service": "generation",
        "request_id": rid,
    }
    resp = JSONResponse(
        status_code=status_code,
        content=body,
        media_type="application/problem+json",
    )
    resp.headers["X-Request-ID"] = rid
    return resp


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return problem_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            title="Validation error",
            detail="คำขอไม่ถูกต้องตามรูปแบบที่กำหนด",
        )

    @app.exception_handler(AppValidationError)
    async def app_validation_handler(request: Request, exc: AppValidationError):
        return problem_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            title="Validation error",
            detail=exc.detail,
        )

    @app.exception_handler(LLMUnavailable)
    async def llm_unavailable_handler(request: Request, exc: LLMUnavailable):
        return problem_response(
            request,
            status_code=503,
            code="LLM_UNAVAILABLE",
            title="LLM unavailable",
            detail=str(exc) or "ผู้ให้บริการ LLM ทั้งหมดไม่พร้อมใช้งานในขณะนี้",
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        return problem_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            title="Internal error",
            detail="เกิดข้อผิดพลาดภายในระบบ",
        )
