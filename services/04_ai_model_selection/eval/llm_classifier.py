"""
D5 — วิธีที่ 3: ถาม LLM ตรง ๆ ให้จำแนก intent (few-shot prompt ผ่าน Groq/Gemini เดิม)

ใช้ app.llm_client.call_general_ai ตัวเดียวกับ /general (ได้ fallback Groq→Gemini ฟรี)
แค่เปลี่ยน system prompt ให้ตอบ JSON เดียว: {"intent": "..."}
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm_client import call_general_ai  # noqa: E402

INTENTS = [
    "trivia_history",
    "match_result",
    "fixture_schedule",
    "standings_stats",
    "weekly_summary",
    "general_football",
    "prediction",
    "out_of_scope",
]

SYSTEM_PROMPT = (
    "คุณเป็นตัวจำแนกประเภทคำถาม (intent classifier) สำหรับผู้ช่วยฟุตบอล Premier League\n"
    f"จำแนกคำถามให้อยู่ใน 1 ใน 8 หมวดนี้เท่านั้น: {', '.join(INTENTS)}\n"
    'ตอบเป็น JSON บรรทัดเดียวเท่านั้น รูปแบบ: {"intent": "<หนึ่งใน 8 ค่าข้างบน>"} '
    "ห้ามมีข้อความอื่นนอกจาก JSON นี้"
)


def classify_one(text: str, request_id: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]
    content, _model, _usage = call_general_ai(messages=messages, max_tokens=50, request_id=request_id)
    match = re.search(r'"intent"\s*:\s*"(\w+)"', content)
    label = match.group(1) if match else content.strip()
    return label if label in INTENTS else "out_of_scope"  # กันโมเดลตอบนอกรายการ


def train_and_eval(X_test, y_test) -> float:
    """LLM แบบ few-shot ไม่ต้อง "เทรน" — เรียกตรงต่อประโยคแล้ววัด accuracy บน test set เลย"""
    correct = 0
    for i, (text, true_label) in enumerate(zip(X_test, y_test)):
        pred = classify_one(text, request_id=f"eval-llm-{i}")
        if pred == true_label:
            correct += 1
    return correct / len(y_test)
