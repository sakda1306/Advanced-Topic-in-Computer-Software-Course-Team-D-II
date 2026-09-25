"""
Config สำหรับ service `engines` (04_ai_engines)
ค่าทั้งหมดตาม CONTRACT.md §8 — ใช้ไลบรารี `openai` ตัวเดียว สลับเจ้าด้วย base_url เท่านั้น
ห้ามลง SDK ของเจ้าอื่นเพิ่ม
"""
import os


class Settings:
    SERVICE_NAME = "engines"
    VERSION = os.getenv("GIT_SHA", "0.1.0")

    # Groq — หลัก
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Gemini — สำรอง
    GEMINI_BASE_URL = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # งบเวลา: router → engines เพดาน 25s ต่อ hop (CONTRACT.md §0)
    # เผื่อพอสำหรับ primary + fallback หนึ่งครั้งภายในเพดานนั้น
    PRIMARY_TIMEOUT_SECONDS = float(os.getenv("GENERAL_PRIMARY_TIMEOUT_SECONDS", "12"))
    FALLBACK_TIMEOUT_SECONDS = float(os.getenv("GENERAL_FALLBACK_TIMEOUT_SECONDS", "10"))

    # D2: ยังไม่จำกัด token อย่างเข้มงวด (ของ D4) แต่ตั้งเพดานกันหลุดไว้ก่อน
    GENERAL_MAX_TOKENS = int(os.getenv("GENERAL_MAX_TOKENS", "600"))


settings = Settings()
