"""ตรวจ pattern prompt injection ในเนื้อ context — ไม่ตัดทิ้ง แค่ log"""
from __future__ import annotations

import re

INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"ignore the above",
    r"disregard (all )?(previous|prior) instructions",
    r"ลืมคำสั่งก่อนหน้า",
    r"เพิกเฉยคำสั่งก่อนหน้า",
    r"system prompt",
    r"you are now",
    r"act as",
    r"new instructions?:",
]


def detect_injection(text: str) -> bool:
    for pat in INJECTION_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            return True
    return False


def detect_prompt_leak(answer: str, canary: str) -> bool:
    """คำตอบมี canary token ของ system prompt หรือไม่"""
    return bool(canary and canary in answer)
