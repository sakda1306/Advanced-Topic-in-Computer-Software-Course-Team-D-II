"""GET /health (CONTRACT §0)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import Settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    return {"status": "ok", "service": settings.service_name, "version": settings.version}
