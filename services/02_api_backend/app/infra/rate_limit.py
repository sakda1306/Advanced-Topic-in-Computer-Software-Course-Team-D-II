"""Per-key fixed-window rate limit (CONTRACT §1: /api/chat 20 per minute per user)."""

from __future__ import annotations

from app.core.errors import AppError, ErrorCode
from app.infra.store import Store

WINDOW_SECONDS = 60


async def enforce_rate_limit(store: Store, bucket: str, key: str, limit_per_minute: int) -> None:
    count, reset_in = await store.hit(f"rl:{bucket}:{key}", WINDOW_SECONDS)
    if count > limit_per_minute:
        raise AppError(ErrorCode.RATE_LIMITED, retry_after=reset_in)
