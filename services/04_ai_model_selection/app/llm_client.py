"""
เรียก LLM ผ่านไลบรารี `openai` ตัวเดียว สลับเจ้าด้วย base_url (CONTRACT.md §8)
ลำดับ: Groq (หลัก) → error/429/timeout → Gemini (สำรอง) 1 ครั้ง → ล่มทั้งคู่ → LLMUnavailableError (ให้ router 503)
"""
import logging
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .config import settings

logger = logging.getLogger("engines")


class LLMUnavailableError(Exception):
    """ทั้ง Groq และ Gemini เรียกไม่สำเร็จ — main.py แปลงเป็น 503 LLM_UNAVAILABLE"""


def _client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key or "missing-key")


def _try_provider(
    *,
    provider: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
    messages: list[dict],
    max_tokens: int,
    request_id: str,
) -> tuple[str, str, dict]:
    """คืน (content, model, token_usage_dict) หรือ raise ให้ผู้เรียกไปลอง provider ถัดไป"""
    client = _client(base_url, api_key)
    t0 = time.monotonic()
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    ms = int((time.monotonic() - t0) * 1000)
    choice = resp.choices[0].message.content or ""
    usage = resp.usage
    token_usage = {
        "input": getattr(usage, "prompt_tokens", 0) or 0,
        "output": getattr(usage, "completion_tokens", 0) or 0,
    }
    logger.info(
        '{"event":"llm_call_ok","provider":"%s","model":"%s","ms":%d,"request_id":"%s"}',
        provider,
        model,
        ms,
        request_id,
    )
    return choice, model, token_usage


def call_general_ai(
    *, messages: list[dict], max_tokens: int, request_id: str
) -> tuple[str, str, dict]:
    """
    ลอง Groq ก่อน ถ้า error / 429 / timeout ค่อยลอง Gemini หนึ่งครั้ง
    ทั้งคู่ล่ม -> LLMUnavailableError
    """
    retryable = (APITimeoutError, RateLimitError, APIConnectionError, APIStatusError)

    try:
        return _try_provider(
            provider="groq",
            base_url=settings.GROQ_BASE_URL,
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL,
            timeout=settings.PRIMARY_TIMEOUT_SECONDS,
            messages=messages,
            max_tokens=max_tokens,
            request_id=request_id,
        )
    except retryable as primary_err:
        logger.warning(
            '{"event":"llm_call_fallback","provider":"groq","error":"%s","request_id":"%s"}',
            str(primary_err),
            request_id,
        )
        try:
            return _try_provider(
                provider="gemini",
                base_url=settings.GEMINI_BASE_URL,
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                timeout=settings.FALLBACK_TIMEOUT_SECONDS,
                messages=messages,
                max_tokens=max_tokens,
                request_id=request_id,
            )
        except retryable as fallback_err:
            logger.error(
                '{"event":"llm_call_failed","provider":"gemini","error":"%s","request_id":"%s"}',
                str(fallback_err),
                request_id,
            )
            raise LLMUnavailableError(
                f"groq: {primary_err} | gemini: {fallback_err}"
            ) from fallback_err
