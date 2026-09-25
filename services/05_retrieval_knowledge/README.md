# 05 Retrieval / Knowledge · `retrieval`

ค้นคลังความรู้ฟุตบอลแบบ hybrid (BM25 + FAISS + RRF) ให้ router ตาม [`docs/CONTRACT.md`](../../docs/CONTRACT.md) §4 และรับเอกสารจาก 07 ตาม §6 · แบบระบบอยู่ที่ [`docs/05_RETRIEVAL_DESIGN.md`](../../docs/05_RETRIEVAL_DESIGN.md)

| endpoint | ตาม | สถานะ |
|---|---|---|
| `POST /search` | §4 | ใช้ได้ |
| `GET /health` · `GET /ready` | §0 · healthcheck ของ compose | ใช้ได้ |
| `POST /index/upsert` · `DELETE /index/{doc_id}` · `GET /index/stats` | §6 | ใช้ได้ |
| `POST /index/rebuild` · `GET /index/jobs/{job_id}` | §6 | PR ②b |

## ตัวแก้ปัญหาจาก week5 ที่อยู่ใน service นี้

| # | ปัญหา | อยู่ที่ |
|---|---|---|
| 1 | vocabulary mismatch | `app/search/aliases.py` — ชื่อเล่นทีมไทย/อังกฤษ → ชื่อทางการในคำค้น BM25 · ฝั่ง vector ใช้โมเดล multilingual กับคำถามเดิม |
| 2 | data quality | `app/kb/trivia.py` — 1,996 ข้อ → ตัดข้อซ้ำ 39 · ตัดข้อขัดแย้ง 2 กลุ่ม (523/1839, 1804/1838) → 1,953 เอกสาร · เอกสารข้อมูลสด upsert ทับด้วย doc_id |
| 3 | chunking | `app/kb/chunking.py` — trivia 1 คู่ถาม-ตอบ = 1 chunk · เอกสารอื่นตัดที่ `## ` |
| 5 | golden set เอียง | PR ③ (`scripts/eval_retrieval.py`) |

## ตัวแปร env

| ชื่อ | ค่าเริ่มต้น | หมายเหตุ |
|---|---|---|
| `KB_DB_PATH` | `/data/kb.sqlite` | อยู่ใน volume |
| `TRIVIA_FILE` | `data/football_trivia_qa.txt` | |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | เปลี่ยนแล้วตอนเริ่มจะ embed ใหม่ทั้งหมดเอง |
| `HF_HOME` | ค่าของไลบรารี | ชี้ไปที่ volume เพื่อไม่ต้องดาวน์โหลดโมเดลทุกครั้ง |
| `RERANK_MODEL` | ว่าง | ว่าง = ปิด · เช่น `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| `MIN_VECTOR_SCORE` | `0.0` | 0 = ปิด · ค่าจริงมาจาก eval (MiniLM ให้ cosine ไทย-อังกฤษต่ำ ราว 0.26) |
| `CANDIDATE_K` · `RRF_K` | `20` · `60` | |
| `FOOTBALL_DATA_URL` | `http://football-data:8000` | ดึงชื่อเล่นทีมจาก `GET /football/teams` · ว่าง = ใช้ไฟล์สำรองอย่างเดียว |
| `ALIASES_CACHE_SECONDS` · `ALIASES_RETRY_SECONDS` | `3600` · `60` | ดึงใหม่ทุกกี่วินาที · ดึงไม่ได้แล้วลองใหม่ในกี่วินาที |
| `ALIASES_TIMEOUT_SECONDS` | `3` | |
| `GIT_SHA` | `0.1.0` | ค่า `version` ใน `/health` |

## รัน

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/pip
export KB_DB_PATH=./.hf-cache/kb.sqlite HF_HOME=./.hf-cache
python -m scripts.ingest_trivia                                   # ครั้งแรกราว 1–2 นาที ครั้งต่อไปข้ามทั้งหมด
uvicorn app.main:app --port 8005 --workers 1                      # เอกสาร API: http://localhost:8005/docs
```

**ใน docker compose** (Dockerfile / compose เป็นของ member6): command `sh scripts/entrypoint.sh` · **worker เดียวเท่านั้น** (index อยู่ในหน่วยความจำของ process) · volume ที่ `/data` และ `HF_HOME` · healthcheck `GET /ready` ตั้ง `start_period` ให้พอ ingest ครั้งแรก (ราว 3 นาที) · ถ้าโมเดลอยู่ใน volume แล้ว ตั้ง `HF_HUB_OFFLINE=1` ได้ ไม่งั้นทุกครั้งที่เริ่มจะเช็ก Hugging Face ผ่านเน็ต

## เทส

```bash
pytest -q                 # ใช้ FakeEmbedder ไม่ต้องโหลดโมเดล
pytest -q -m model        # โมเดลจริงกับคลังจริง
RETRIEVAL_URL=http://localhost:8005 python scripts/smoke.py   # รวม upsert → search → delete ด้วยเอกสารทดสอบที่ลบคืนเอง
ruff check . && ruff format --check .
```

## จุดที่ควรรู้

- **SQLite คือแหล่งจริง** FAISS + BM25 เป็น snapshot ในหน่วยความจำที่สร้างจากชุด chunk เดียวกัน แล้วสลับทีเดียว `/search` ไม่เคยเห็น index ครึ่ง ๆ
- **05 ไม่ผ่อน filter เอง** ไม่เจอ = `200` + `chunks: []` การค้นซ้ำโดยตัด matchweek เป็นของ router (§3)
- **filter ที่ไม่รู้จัก → 422** เพื่อไม่ให้ filter ที่พิมพ์ผิดคืนผลแบบไม่กรอง
- **ชื่อเล่นทีมมาจาก 07** task เบื้องหลังดึง `GET /football/teams` ทุก `ALIASES_CACHE_SECONDS` `/search` ไม่เคยรอ 07 · ก่อน 07 ตอบ หรือ 07 ล่ม / ตอบชุดว่าง ใช้ `data/team_aliases.json` (หรือชุดล่าสุดที่ดึงได้)
- **upsert และ delete สำเร็จหรือไม่สำเร็จทั้งก้อน** embed และสร้าง snapshot ใหม่ก่อนเขียน SQLite ขั้นไหนล้ม → 500 และทั้ง SQLite กับ `/search` ยังเป็นรุ่นเดิม
- **`by_category` ใน `/index/stats` นับเป็นจำนวนเอกสาร** ต่อ category ไม่ใช่จำนวน chunk
