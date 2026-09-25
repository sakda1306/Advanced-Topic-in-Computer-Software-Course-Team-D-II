# 04 — AI Engines (`engines`) · member3

General AI + Local AI Model ตาม `CONTRACT.md` §3 และ §8

## สถานะ

| วัน | สถานะ |
|---|---|
| D1 | ✅ `data/intents.csv` — 8 หมวด × 30 ตัวอย่าง (ไทย+อังกฤษ) |
| D2 | ✅ `POST /general` ใช้ได้จริง · fallback Groq → Gemini |
| D3 | ⬜ `train.py` + `POST /local/classify` |
| D4 | ⬜ ปรับ dataset จาก routing cases จริง · จำกัด token ของ `/general` |
| D5 | ⬜ เทียบ TF-IDF vs embedding vs LLM · (Could) `/local/predict` |
| D6 | ⬜ accuracy ลง README |

## รันเดี่ยว (ไม่ผ่าน Docker Compose)

```bash
cd services/04_ai_engines
pip install -r requirements.txt
cp .env.example .env   # ใส่ GROQ_API_KEY / GEMINI_API_KEY จริง
uvicorn app.main:app --reload --port 8004
```

ทดสอบ:

```bash
curl http://localhost:8004/health

curl -X POST http://localhost:8004/general \
  -H "Content-Type: application/json" \
  -d '{"request_id":"test-1","query":"กฎล้ำหน้าคืออะไร","history":[],"language":"th"}'
```

## เทส

```bash
pytest tests/ -v
```

เทส `/general` mock การเรียก LLM ทั้งหมด (ไม่ยิง API จริง) ครอบคลุม:
- ตอบสำเร็จจาก Groq (primary) — ไม่แตะ Gemini เลย
- Groq timeout/error → fallback ไป Gemini อัตโนมัติ
- ทั้งคู่ล่ม → ตอบ `503` รูปแบบ Problem-JSON พร้อม `code: LLM_UNAVAILABLE`
- history ถูกส่งเข้า context ถูกต้อง (จำกัด 10 ข้อความล่าสุด) และ system prompt สลับตาม `language`
- ขาด field บังคับ (`query`) → `422`

## หมายเหตุการออกแบบ D2

- ใช้ไลบรารี `openai` ตัวเดียวทั้งสอง provider ตาม CONTRACT.md §8 (ห้ามลง SDK เจ้าอื่นเพิ่ม) — สลับด้วย `base_url` เท่านั้น
- ลำดับ fallback: **Groq → (timeout/429/connection/status error) → Gemini ครั้งเดียว → ทั้งคู่ล่ม = `LLM_UNAVAILABLE` (503)**
- ทุก response ที่มาจาก LLM คืน `model` ที่ใช้จริง (ไม่ใช่ชื่อ provider) และ `token_usage` ตาม contract
- `/general` เป็นเส้นสำหรับคำถามฟุตบอลทั่วไปที่คลัง (RAG) ไม่ครอบคลุม — system prompt กำชับไม่ให้เดาผลบอล/ตารางคะแนน เพราะข้อมูลสดต้องมาจากเส้น `football_rag` เท่านั้น (ตาม "ลำดับถอย" ใน CONTRACT.md §3 ที่ห้าม intent ข้อมูลแมตช์ถอยมาที่ `general_ai`)
- `X-Request-ID`: middleware สร้างให้ถ้าไม่มีมา, ใส่กลับใน response header, และ log ทุก event เป็น JSON บรรทัดเดียว ตาม CONTRACT.md §0
- error ทุกกรณีตอบ Problem-JSON (`application/problem+json`) ตามรูปแบบเดียวกับ service อื่น
- `GENERAL_MAX_TOKENS` ตั้งไว้แบบกันหลุดเบื้องต้น (600) — การจำกัด token แบบจริงจัง (ต่อ request/ต่อ user) เป็นงานของ D4

## ยังไม่ได้ทำใน D2 (ตั้งใจเว้นไว้)

- `POST /local/classify`, `POST /local/predict` — D3/D5
- token budget ต่อ user/ต่อ request แบบเข้ม — D4
- `Dockerfile` — เจ้าของคือ member6 ตาม `GIT_FLOW.md` (ไม่แก้ในโฟลเดอร์นี้)
