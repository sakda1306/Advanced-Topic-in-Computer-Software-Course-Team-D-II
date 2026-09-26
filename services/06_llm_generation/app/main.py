"""FastAPI app entrypoint — service 06 · LLM Generation"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.errors import register_error_handlers
from app.middleware import RequestIDMiddleware, log_event
from app.routes import generate, health, report


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: ตรวจว่าโมเดลยังมีอยู่ (background, ไม่ทำให้ service ล้ม, /health ต้องตอบ ok เสมอ)
    if not settings.llm_mock:
        from app.llm.client import RealLLMClient

        client = RealLLMClient(settings)
        asyncio.create_task(client.check_models_available())
    log_event("startup", "-", service="generation", version=settings.service_version)
    yield


app = FastAPI(title="06 · LLM Generation", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
register_error_handlers(app)

app.include_router(health.router)
app.include_router(generate.router)
app.include_router(report.router)
