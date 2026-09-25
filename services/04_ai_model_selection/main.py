import os
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from openai import AsyncOpenAI, OpenAIError

app = FastAPI(title="AI Engines Service", version="0.1.0")

# --- Configuration & Environment Variables ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Setup OpenAI Clients according to CONTRACT.md §8
groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY or "dummy_key",
    base_url="https://api.groq.com/openai/v1"
)

gemini_client = AsyncOpenAI(
    api_key=GEMINI_API_KEY or "dummy_key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)


# --- Pydantic Data Models (CONTRACT.md §0 & §3) ---
class HistoryMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class GeneralRequest(BaseModel):
    request_id: str
    query: str
    history: List[HistoryMessage] = []
    language: Optional[str] = "th"


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0


class EngineResult(BaseModel):
    engine: str = "general_ai"
    content: str
    data: Optional[dict] = None
    sources: List[dict] = []
    model: str
    latency_ms: int
    token_usage: TokenUsage


# --- Health Check Endpoint (CONTRACT.md §0) ---
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "engines",
        "version": "0.1.0"
    }


# --- POST /general Endpoint ---
@app.post("/general", response_model=EngineResult)
async def general_ai_endpoint(req: GeneralRequest):
    start_time = time.time()
    
    system_prompt = (
        "You are a helpful football assistant specialized in Premier League. "
        "Answer the user's question clearly, accurately, and politely in the requested language."
    )
    if req.language == "th":
        system_prompt += " Respond in Thai."

    # Construct messages array
    messages = [{"role": "system", "content": system_prompt}]
    for msg in req.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.query})

    # 1. Primary Attempt: Groq
    if GROQ_API_KEY:
        try:
            response = await groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                timeout=20.0
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            content = response.choices[0].message.content or ""
            usage = response.usage
            token_usage = TokenUsage(
                input=usage.prompt_tokens if usage else 0,
                output=usage.completion_tokens if usage else 0
            )

            return EngineResult(
                engine="general_ai",
                content=content,
                data=None,
                sources=[],
                model=f"groq/{GROQ_MODEL}",
                latency_ms=elapsed_ms,
                token_usage=token_usage
            )
        except Exception as e:
            print(f"[Warning] Groq primary LLM failed: {e}. Falling back to Gemini...")

    # 2. Fallback Attempt: Gemini
    if GEMINI_API_KEY:
        try:
            response = await gemini_client.chat.completions.create(
                model=GEMINI_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                timeout=20.0
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            content = response.choices[0].message.content or ""
            usage = response.usage
            token_usage = TokenUsage(
                input=usage.prompt_tokens if usage else 0,
                output=usage.completion_tokens if usage else 0
            )

            return EngineResult(
                engine="general_ai",
                content=content,
                data=None,
                sources=[],
                model=f"gemini/{GEMINI_MODEL}",
                latency_ms=elapsed_ms,
                token_usage=token_usage
            )
        except Exception as e:
            print(f"[Error] Gemini fallback LLM failed: {e}")

    # 3. All Providers Failed
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "type": "https://errors.football-assistant.local/llm-unavailable",
            "title": "LLM Provider Unavailable",
            "status": 503,
            "code": "LLM_UNAVAILABLE",
            "detail": "ไม่สามารถเชื่อมต่อกับบริการ AI ได้ในขณะนี้ ทั้ง Groq และ Gemini",
            "service": "engines",
            "request_id": req.request_id
        }
    )