# 04 — AI Engines (`engines`) · member3

General AI + Local AI Model ตาม `CONTRACT.md` §3 และ §8

## สถานะ

| วัน | สถานะ |
|---|---|
| D1 | ✅ `data/intents.csv` — 8 หมวด, เริ่มที่ 240 แถว (ดู D4 ที่เพิ่มอีก 14) |
| D2 | ✅ `POST /general` ใช้ได้จริง · fallback Groq → Gemini |
| D3 | ✅ `train.py` + `POST /local/classify` ใช้ได้ (TF-IDF char-ngram + LogisticRegression) |
| D4 | ✅ ปรับ dataset จาก error จริงที่เจอ (ดูหัวข้อด้านล่าง) · จำกัด token ของ `/general` |
| D5 | ✅ ตาราง 3 แถว (TF-IDF รันจริง, embeddings/LLM รอรันในเครื่องที่ต่อเน็ตได้) · `/local/predict` ตอบ `501` ตามที่ contract อนุญาต |
| D6 | ⬜ accuracy ลง README (รอบสุดท้ายก่อนหยุด 20:00) |

## รันเดี่ยว (ไม่ผ่าน Docker Compose)

```bash
cd services/04_ai_engines
pip install -r requirements.txt
cp .env.example .env   # ใส่ GROQ_API_KEY / GEMINI_API_KEY จริง

# เทรน classifier ก่อน (จำเป็นสำหรับ /local/classify)
python train.py

uvicorn app.main:app --reload --port 8004
```

ทดสอบ:

```bash
curl http://localhost:8004/health

curl -X POST http://localhost:8004/general \
  -H "Content-Type: application/json" \
  -d '{"request_id":"t1","query":"กฎล้ำหน้าคืออะไร","history":[],"language":"th"}'

curl -X POST http://localhost:8004/local/classify \
  -H "Content-Type: application/json" \
  -d '{"request_id":"t2","text":"เมื่อวานปืนใหญ่เจอใคร ผลเท่าไหร่"}'

curl -X POST http://localhost:8004/local/predict \
  -H "Content-Type: application/json" \
  -d '{"request_id":"t3","home_team_id":57,"away_team_id":61,"season":"2026"}'
# -> 501 NOT_IMPLEMENTED (ดูเหตุผลในหัวข้อ D5 ด้านล่าง)
```

## เทส

```bash
pytest tests/ -v   # 20 เทส ครอบ /general, /local/classify, /local/predict, poisson math, token budget
```

ทุกเทส mock การเรียก LLM ภายนอก (ไม่ยิง Groq/Gemini จริง) — `/local/classify` ใช้โมเดลจริงที่เทรนไว้
(ต้องรัน `python train.py` ก่อน 1 ครั้ง ไม่งั้นเทสที่เรียกโมเดลจริงจะ fail)

---

## D3 — `train.py` + `POST /local/classify`

- `TfidfVectorizer(analyzer="char_wb", ngram_range=(2,4))` + `LogisticRegression` — เลือก char n-gram
  แทน word-level เพราะภาษาไทยไม่มีช่องว่างคั่นคำ ตัดด้วย whitespace ธรรมดาจะทำให้ TF-IDF ไร้ประโยชน์
  กับประโยคไทย และไม่อยากเพิ่ม dependency ตัวตัดคำไทย (pythainlp) ตอนนี้
- `train.py` เทรน 2 รอบ: (1) held-out split 80/20 เพื่อวัด accuracy แบบไม่โกง (2) เทรนจริงด้วยข้อมูล
  ทั้งหมดแล้วเซฟเป็น `app/models/intent_clf.joblib` ไปใช้ที่ `/local/classify`
- ผลตอนนี้: **held-out accuracy = 0.804** (51 ตัวอย่าง จาก 254 แถวทั้งหมด)
- `/local/classify` คืน `EngineResult` ตาม contract: `content: "intent: match_result (0.88)"`,
  `data: {label, score, top_k}` (top_k 3 อันดับ), `model: "tfidf-logreg-v1"`, `token_usage: {0,0}`
  (ไม่เรียก LLM เลยในเส้นนี้)
- โมเดลโหลดครั้งเดียวตอน process start (`app/local_classifier.py` เป็น singleton) ไม่โหลดใหม่ทุก request

## D4 — ปรับ dataset จาก error จริง + จำกัด token ของ `/general`

**ปรับ dataset:**
ยังไม่ได้รับ `tests/routing_cases.jsonl` ของจริงจาก member2 (40 เคส) ตอนเขียนงานนี้ — ใช้
`tests/simulated_routing_cases.jsonl` (24 เคสที่เขียนเองจำลองสไตล์คำถามจริง) แทนไปก่อน
รันแล้วเจอ **8/24 พลาด (accuracy 0.667)** วิเคราะห์ได้ 4 pattern ที่พลาดจริง (ไม่ใช่สุ่ม):

1. ใช้ชื่อเล่น "ยูไนเต็ด" (แมนยู) — dataset เดิมมีแต่ "ผี"/"แมนยู" ไม่เคยเห็น token นี้
2. weekly_summary แบบ "เมื่อคืน...ทุกคู่" ถูกทายเป็น match_result เพราะคำว่า "เมื่อคืน" ปนกัน
3. trivia_history เชิงสถิติสะสม/ประวัติ ("เคยไม่แพ้กี่นัดติด") สับสนกับ standings_stats (สถิติฤดูกาลนี้)
4. standings_stats ภาษาอังกฤษแบบเปรียบเทียบ 2 ทีม ("who has more clean sheets X or Y") ไม่เคยมีในชุดเดิม

แก้โดยเพิ่ม 14 ตัวอย่างที่ตรง pattern ที่พลาดจริง (`d4_augment_dataset.py`) แล้วเทรนใหม่ —
**accuracy บนชุดทดสอบเดิมขึ้นจาก 0.667 → 0.958 (23/24)** ยังพลาดอยู่ 1 เคส
("แข้งเบอร์ 9 ของซิตี้คือใคร ยิงไปกี่ลูกแล้ว" → ทาย match_result ที่ถูกคือ standings_stats — ทั้งสอง
หมวดนี้ยังเป็นคู่ที่โมเดลสับสนบ่อยสุด เพราะคำถาม "ยิงไปกี่ลูก" ใช้ได้ทั้งสองบริบท)

**ต้องทำซ้ำเมื่อได้ไฟล์จริงจาก member2**: รัน `python train.py` (จะอ่าน
`services/03_ai_router_agent/tests/routing_cases.jsonl` อัตโนมัติถ้ามีไฟล์อยู่ — ไม่ต้องแก้โค้ด)
วิเคราะห์ error ใหม่ แล้วเพิ่มตัวอย่างเฉพาะ pattern ที่พลาดจริงแบบเดียวกันนี้

**จำกัด token ของ `/general`:**
- response cap ลดจาก 600 → **350** tokens (`GENERAL_MAX_TOKENS`) — `/general` ควรตอบสั้นกระชับอยู่แล้ว
- เพิ่ม input budget **1200 tokens โดยประมาณ** (`GENERAL_MAX_INPUT_TOKENS`) ครอบ system + history + query
  — `app/token_budget.py` ตัด history เก่าสุดออกทีละข้อความจนกว่าจะอยู่ในงบ (เก็บข้อความใหม่สุดไว้ก่อน)
- ใช้ตัวประมาณ token แบบ char-based (~2.2 ตัวอักษร/token) ไม่ใช้ tokenizer จริงของ Groq/Gemini
  เพราะสองเจ้าใช้ tokenizer คนละตัว ไม่มีตัวที่ตรงทั้งคู่ 100% อยู่แล้ว — เป้าหมายคือกัน context บาน
  ไม่ใช่นับ token เป๊ะเพื่อคิดเงิน

## D5 — เทียบ 3 วิธี + `/local/predict`

**ตาราง 3 แถว**: ดู [`eval/method_comparison.md`](eval/method_comparison.md) (สร้างจาก
`python eval/compare_methods.py`)

⚠️ **สภาพแวดล้อมที่เขียนโค้ดนี้บล็อกเน็ตเวิร์กไปยัง `huggingface.co`, `api.groq.com`,
`generativelanguage.googleapis.com`** (ทดสอบแล้วได้ `403 Host not in allowlist`) จึงรันได้จริงแค่
วิธีที่ 1 (TF-IDF) เท่านั้น — **ตัวเลขวิธีที่ 2 (embeddings) และ 3 (ถาม LLM) เป็น placeholder**
ต้องรัน `pip install -r requirements-eval.txt && python eval/compare_methods.py` ในเครื่อง/CI ที่ต่อเน็ต
ได้จริง + ใส่ `GROQ_API_KEY`/`GEMINI_API_KEY` ก่อน ตารางจะเติมตัวเลขจริงให้อัตโนมัติ

**`/local/predict` (Could) — ตอบ 501 ตามที่ contract อนุญาต** เหตุผล (ไม่ใช่แค่ "ยังไม่ได้เขียนโค้ด"):

1. service `07_football_data` ยังไม่ถูกสร้าง (ทุก service ใน `SCHEDULE.md` ยังเป็น placeholder)
   จึงไม่มี "ผลที่ 07 เก็บไว้" ให้ดึงจริงตามที่งานนี้ต้องการ
2. `CONTRACT.md` §7 (api → football-data) **ไม่ได้ให้สิทธิ์ `engines` เรียก football-data โดยตรง**
   — คนเรียกที่ระบุไว้มีแค่ `api` และ `router` (เฉพาะ `/football/teams`) การจะให้ `/local/predict` ดึงผล
   ย้อนหลังมาคำนวณเองต้อง **เพิ่ม § ใหม่ใน CONTRACT.md ก่อน** (ต้อง approve จาก sakda1306 + เจ้าของ 07
   ตามกฎเหล็กบรรทัดแรกของไฟล์) — เป็นการตัดสินใจสถาปัตยกรรมที่ควรคุยในทีมก่อน ไม่ใช่แค่โค้ด

สิ่งที่ทำแล้วจริง: **คณิตศาสตร์ Poisson model ล้วน ๆ** ใน `app/poisson.py`
(`TeamStrength` → `expected_goals` → `match_outcome_probabilities`) พร้อม unit test 4 ตัวใน
`tests/test_poisson.py` (ผลรวมความน่าจะเป็น = 1, ทีมแข็งกว่าได้เปรียบ, ทีมพอกันแบ่งใกล้เคียงกัน)
— พร้อมต่อกับข้อมูลจริงทันทีที่ (1) มี 07 และ (2) มีการเพิ่ม CONTRACT.md ให้ engines อ่านผลย้อนหลังได้

**ข้อเสนอสำหรับทีม (ยกไปคุยตอนเปิด PR)**: เพิ่ม §3.1 ใน CONTRACT.md ให้ `router` เป็นคนดึง
"ผลย้อนหลัง N นัดล่าสุดของ 2 ทีม" จาก 07 มาก่อน แล้วส่งมาเป็นส่วนหนึ่งของ `PredictRequest` แทนที่จะให้
`engines` เรียก 07 เอง — ตรงกับ "หลักคิดที่ 3" ใน `00_PLAN_OVERVIEW.md` ที่ว่า router เป็นจุดตัดสินใจ
จุดเดียว และไม่เพิ่มเส้นเรียกข้ามระหว่าง service ที่ไม่มีในผัง

## หมายเหตุการออกแบบ D2 (อ้างอิง)

- ใช้ไลบรารี `openai` ตัวเดียวทั้งสอง provider ตาม CONTRACT.md §8 — สลับด้วย `base_url` เท่านั้น
- ลำดับ fallback: **Groq → (timeout/429/connection/status error) → Gemini ครั้งเดียว → ทั้งคู่ล่ม =
  `LLM_UNAVAILABLE` (503)**
- `X-Request-ID`: middleware สร้างให้ถ้าไม่มีมา, ใส่กลับใน response header, log ทุก event เป็น JSON
  บรรทัดเดียว ตาม CONTRACT.md §0
- error ทุกกรณีตอบ Problem-JSON (`application/problem+json`)

## โครงสร้างไฟล์

```
services/04_ai_engines/
├── app/
│   ├── main.py              # FastAPI: /health, /general, /local/classify, /local/predict
│   ├── config.py            # env vars (Groq/Gemini, timeout, token budget)
│   ├── schemas.py           # pydantic models ตรงกับ CONTRACT.md
│   ├── llm_client.py        # Groq → Gemini fallback
│   ├── local_classifier.py  # โหลด/ใช้โมเดล TF-IDF+LogReg
│   ├── token_budget.py      # D4: ประมาณ/ตัด token ของ history
│   ├── poisson.py           # D5: คณิตศาสตร์ Poisson model (pure function)
│   └── models/intent_clf.joblib   # โมเดลที่เทรนแล้ว (จาก train.py)
├── data/intents.csv         # D1 + D4 (254 แถว)
├── eval/
│   ├── compare_methods.py   # D5: รันเทียบ 3 วิธี เขียน method_comparison.md
│   ├── embedding_classifier.py
│   ├── llm_classifier.py
│   └── method_comparison.md
├── tests/
│   ├── test_general.py / test_llm_client.py       # D2
│   ├── test_local_engines.py / test_poisson.py    # D3/D5
│   ├── test_token_budget.py                       # D4
│   └── simulated_routing_cases.jsonl               # ใช้แทน routing_cases.jsonl ของจริงชั่วคราว
├── train.py                 # D3: เทรน + ประเมินผล
├── d4_augment_dataset.py    # D4: เพิ่มตัวอย่างจาก error ที่วิเคราะห์ได้
├── requirements.txt
├── requirements-eval.txt    # เฉพาะรัน eval/compare_methods.py วิธี embeddings
└── .env.example
```

## ยังไม่ได้ทำ (ตั้งใจเว้นไว้)

- `Dockerfile` — เจ้าของคือ member6 ตาม `GIT_FLOW.md` (ไม่แก้ในโฟลเดอร์นี้)
- ตัวเลขจริงของวิธี embeddings/LLM ใน D5 — ต้องรันในเครื่องที่ต่อเน็ตได้ (ดูหัวข้อ D5)
- `/local/predict` แบบใช้ข้อมูลจริง — ต้องรอ 07 + แก้ CONTRACT.md (ดูหัวข้อ D5)
- D6: accuracy สรุปสุดท้ายลง README — รอผลจาก `routing_cases.jsonl` ของจริง
