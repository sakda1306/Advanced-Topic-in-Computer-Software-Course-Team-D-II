# 05 Retrieval / Knowledge · `retrieval`

ค้นคลังความรู้ฟุตบอลแบบ hybrid (BM25 + FAISS + RRF) ให้ router ตาม [`docs/CONTRACT.md`](../../docs/CONTRACT.md) §4 · แบบระบบอยู่ที่ [`docs/05_RETRIEVAL_DESIGN.md`](../../docs/05_RETRIEVAL_DESIGN.md)

| endpoint | ตาม | สถานะ |
|---|---|---|
| `POST /search` | §4 | ใช้ได้ |
| `GET /health` · `GET /ready` | §0 · healthcheck ของ compose | ใช้ได้ |
| `POST /index/upsert` · `DELETE /index/{doc_id}` · `GET /index/stats` · `POST /index/rebuild` · `GET /index/jobs/{job_id}` | §6 | PR ② |

## ตัวแก้ปัญหาจาก week5 ที่อยู่ใน service นี้

| # | ปัญหา | อยู่ที่ |
|---|---|---|
| 1 | vocabulary mismatch | `app/search/aliases.py` — ชื่อเล่นทีมไทย/อังกฤษ → ชื่อทางการในคำค้น BM25 · ฝั่ง vector ใช้โมเดล multilingual กับ `query` ที่ router เขียนเป็นอังกฤษ (ดูผลวัด) |
| 2 | data quality | `app/kb/trivia.py` — 1,996 ข้อ → ตัดข้อซ้ำ 39 · ตัดข้อขัดแย้ง 2 กลุ่ม (523/1839, 1804/1838) → 1,953 เอกสาร · เอกสารข้อมูลสด upsert ทับด้วย doc_id |
| 3 | chunking | `app/kb/chunking.py` — trivia 1 คู่ถาม-ตอบ = 1 chunk · เอกสารอื่นตัดที่ `## ` |
| 5 | golden set เอียง | `scripts/build_golden.py` + `scripts/eval_retrieval.py` — 60 ข้อจริงตามสัดส่วนหมวดของคลัง · partial เก็บหัวข้อไม่ใช่คำขึ้นต้นประโยค · ผลอยู่ในหัวข้อ "ผลวัด" ด้านล่าง |

## ตัวแปร env

| ชื่อ | ค่าเริ่มต้น | หมายเหตุ |
|---|---|---|
| `KB_DB_PATH` | `/data/kb.sqlite` | อยู่ใน volume |
| `TRIVIA_FILE` | `data/football_trivia_qa.txt` | |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | เปลี่ยนแล้วตอนเริ่มจะ embed ใหม่ทั้งหมดเอง |
| `HF_HOME` | ค่าของไลบรารี | ชี้ไปที่ volume เพื่อไม่ต้องดาวน์โหลดโมเดลทุกครั้ง |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ว่าง = ปิด · เลือกจากผลวัดด้านล่าง · image ควรดาวน์โหลดไว้ใน `HF_HOME` พร้อม embedding model |
| `MIN_VECTOR_SCORE` | `0.0` | 0 = ปิด · ค่าจริงมาจาก eval (MiniLM ให้ cosine ไทย-อังกฤษต่ำ ราว 0.26) |
| `CANDIDATE_K` · `RRF_K` | `20` · `60` | |
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
RETRIEVAL_URL=http://localhost:8005 python scripts/smoke.py
ruff check . && ruff format --check .
```

## ผลวัด (`eval/results/retrieval.json`)

```bash
python -m scripts.build_golden                                     # สร้าง eval/golden_trivia.jsonl ใหม่ (ผลเดิมทุกครั้ง)
python -m scripts.eval_retrieval --kb ./.hf-cache/kb.sqlite \
  --rerank cross-encoder/ms-marco-MiniLM-L-6-v2 --rerank BAAI/bge-reranker-v2-m3
```

วัดในเครื่อง (CPU) กับโมเดลจริง บนสำเนาของคลัง: trivia 1,953 + เอกสารข้อมูลสด**จำลอง** 14 ชิ้น (`eval/fixtures/live_docs.json`) = 1,967 เอกสาร 1,999 chunk · ฝั่ง vector embed `query` · ค่าในตาราง = hit@1 / MRR (hit@5 ≥ 0.90 ทุกช่อง ดูครบใน JSON)

| ชุด (n) | bm25 | vector | hybrid | hybrid + ms-marco | hybrid + bge-m3 |
|---|---|---|---|---|---|
| trivia/verbatim (60) | 1.00 / 1.00 | 0.95 / 0.97 | 0.98 / 0.99 | 1.00 / 1.00 | 1.00 / 1.00 |
| trivia/slang (33) | 0.88 / 0.93 | 0.73 / 0.85 | 0.85 / 0.92 | 0.94 / 0.97 | 0.94 / 0.97 |
| trivia/partial (60) | 0.97 / 0.98 | 0.80 / 0.85 | 0.83 / 0.91 | 0.97 / 0.98 | 0.95 / 0.97 |
| trivia/natural (60) | 0.93 / 0.97 | 0.92 / 0.95 | 0.98 / 0.99 | 1.00 / 1.00 | 0.98 / 0.99 |
| match (20) | 0.90 / 0.93 | 0.90 / 0.93 | 0.90 / 0.95 | 0.95 / 0.97 | 0.95 / 0.97 |

| latency ต่อคำค้น (ใน process) | bm25 | vector | hybrid | hybrid + ms-marco | hybrid + bge-m3 |
|---|---|---|---|---|---|
| p50 ms | 4–8 | 27–35 | 31–43 | 116–257 | 1690–4959 |
| p95 ms | 4–26 | 29–51 | 34–78 | 296–621 | 5100–12757 |

**อ่านผล**
- **trivia ง่ายเกินจริง** คำถามทุกแบบยังสร้างจากข้อความในคลังเอง BM25 จึงแทบเต็ม · ตัวเลขนี้ใช้เทียบโหมด ไม่ใช่คะแนนของผู้ใช้จริง
- **ฝั่ง vector ใช้ `query` แทน `query_original`** เดิม embed คำถามภาษาไทย ชุด match ได้ hybrid 0.70 / vector 0.60 (hit@1) เพราะ MiniLM จับคู่ไทย-อังกฤษอ่อน · เปลี่ยนแล้วเป็น 0.90 / 0.90 และ trivia เท่าเดิม · embed ทั้งสองภาษาแล้วรวม RRF ทำ trivia ตก จึงไม่ใช้ · คำอังกฤษใน golden เขียนมาดี ถ้า router แปลแย่ผลจริงจะต่ำกว่านี้
- **เปิด ms-marco เป็นค่าเริ่มต้น** hit@1 ทุกชุด ≥ 0.94 ที่ p95 ≤ 0.62 วินาที · **bge-m3 แม่นใกล้กันแต่ p95 ถึง 13 วินาที** เกิน timeout router → retrieval 10 วินาที (CONTRACT §0) ใช้บน CPU ไม่ได้
- **`MIN_VECTOR_SCORE` คงไว้ที่ 0.0** — hybrid ไม่เคยตอบ `chunks: []` ให้คำถามนอกคลังเลยที่ทุกค่า เพราะ BM25 ยังเจอคำร่วมอยู่เสมอ ค่าที่สูงขึ้นจึงไม่เปลี่ยนสิ่งที่ router ได้รับ · คำถามนอกคลังต้องให้ router (intent) และ generation (ตอบว่าไม่มีข้อมูล) จัดการ

| MIN_VECTOR_SCORE | hit ที่ถูกโดนตัด | นอกคลังได้ว่าง (vector) | นอกคลังได้ว่าง (hybrid) |
|---|---|---|---|
| 0.00 | 0.0% | 0% | 0% |
| 0.30 | 0.0% | 30% | 0% |
| 0.40 | 0.0% | 40% | 0% |
| 0.50 | 0.4% | 60% | 0% |
| 0.60 | 4.7% | 90% | 0% |

## จุดที่ควรรู้

- **SQLite คือแหล่งจริง** FAISS + BM25 เป็น snapshot ในหน่วยความจำที่สร้างจากชุด chunk เดียวกัน แล้วสลับทีเดียว `/search` ไม่เคยเห็น index ครึ่ง ๆ
- **05 ไม่ผ่อน filter เอง** ไม่เจอ = `200` + `chunks: []` การค้นซ้ำโดยตัด matchweek เป็นของ router (§3)
- **filter ที่ไม่รู้จัก → 422** เพื่อไม่ให้ filter ที่พิมพ์ผิดคืนผลแบบไม่กรอง
- **`data/team_aliases.json` เป็นไฟล์สำรอง** ตัวจริงเป็นของ 07 (PR ② จะดึงจาก `GET /football/teams`)
