"""POST /generate — router(03) เรียก"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response

from app.config import settings
from app.errors import AppValidationError
from app.llm.client import LLMClient
from app.llm.mock import MockLLMClient
from app.pipeline.grounded import run_grounded
from app.pipeline.passthrough import run_passthrough
from app.schemas import GenerateRequest, GenerateResponse

router = APIRouter()


def get_llm_client() -> LLMClient:
    if settings.llm_mock:
        return MockLLMClient()
    from app.llm.client import RealLLMClient

    return RealLLMClient(settings)


def resolve_request_id(body_request_id: str | None, request: Request) -> str:
    """Header X-Request-ID > body.request_id > UUID ใหม่ (หัวข้อ 4.1)"""
    header_rid = request.headers.get("X-Request-ID")
    if header_rid:
        return header_rid
    if body_request_id:
        return body_request_id
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


@router.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest, request: Request, response: Response):
    request_id = resolve_request_id(body.request_id, request)
    response.headers["X-Request-ID"] = request_id
    llm = get_llm_client()

    if body.mode == "grounded":
        return await run_grounded(body, llm=llm, settings=settings, request_id=request_id)
    if body.mode == "passthrough":
        return await run_passthrough(body, llm=llm, settings=settings, request_id=request_id)
    raise AppValidationError(f"mode ไม่รู้จัก: {body.mode}")
