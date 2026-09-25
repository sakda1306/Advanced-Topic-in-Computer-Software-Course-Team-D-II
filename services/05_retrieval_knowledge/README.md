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
| 1 | vocabulary mismatch | `app/search/aliases.py` — ชื่อเล่นทีมไทย/อังกฤษ → ชื่อทางการในคำค้น BM25 · ฝั่ง vector ใช้โมเดล multilingual กับคำถามเดิม |
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
| `RERANK_MODEL` | ว่าง | ว่าง = ปิด · เช่น `cross-encoder/ms-marco-MiniLM-L-6-v2` |
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
python -m scripts.eval_retrieval --kb ./.hf-cache/kb.sqlite   --rerank cross-encoder/ms-marco-MiniLM-L-6-v2 --rerank BAAI/bge-reranker-v2-m3
```

วัดในเครื่อง (CPU) กับโมเดลจริง บนสำเนาของคลัง: trivia 1,953 + เอกสารข้อมูลสด**จำลอง** 14 ชิ้น (`eval/fixtures/live_docs.json`) = 1,967 เอกสาร 1,999 chunk · ค่าในตาราง = hit@1 / MRR (hit@5 ≥ 0.90 ทุกช่อง ดูครบใน JSON)

| ชุด (n) | bm25 | vector | hybrid | hybrid + ms-marco | hybrid + bge-m3 |
|---|---|---|---|---|---|
| trivia/verbatim (60) | 1.00 / 1.00 | 0.95 / 0.97 | 0.98 / 0.99 | 1.00 / 1.00 | 1.00 / 1.00 |
| trivia/slang (33) | 0.88 / 0.93 | 0.73 / 0.85 | 0.85 / 0.92 | 0.94 / 0.97 | 0.94 / 0.97 |
| trivia/partial (60) | 0.97 / 0.98 | 0.80 / 0.85 | 0.83 / 0.91 | 0.97 / 0.98 | 0.95 / 0.97 |
| trivia/natural (60) | 0.93 / 0.97 | 0.92 / 0.95 | 0.98 / 0.99 | 1.00 / 1.00 | 0.98 / 0.99 |
| match (20) | 0.90 / 0.93 | 0.60 / 0.72 | 0.70 / 0.82 | 0.95 / 0.97 | 1.00 / 1.00 |

| latency ต่อคำค้น (ใน process) | bm25 | vector | hybrid | hybrid + ms-marco | hybrid + bge-m3 |
|---|---|---|---|---|---|
| p50 ms | 4–8 | 28–33 | 31–41 | 123–255 | 1677–5321 |
| p95 ms | 5–27 | 33–61 | 38–80 | 335–718 | 6313–13267 |

**อ่านผล**
- **trivia ง่ายเกินจริง** คำถามทุกแบบยังสร้างจากข้อความในคลังเอง BM25 จึงแทบเต็ม · ตัวเลขนี้ใช้เทียบโหมด ไม่ใช่คะแนนของผู้ใช้จริง
- **hybrid แพ้ bm25 ในชุด match (0.70 vs 0.90)** ฝั่ง vector อ่าน `query_original` ภาษาไทย และ MiniLM จับคู่ไทย-อังกฤษได้อ่อน จึงเรียงเอกสารผิดใน set ที่ filter แคบแล้ว แล้ว RRF ดึงขึ้นมา · ไม่ใส่ filter (gm16) เอกสารข้อมูลสดแพ้ trivia ที่พูดถึง Manchester derby
- **ms-marco ดึงทุกชุดกลับมา ≥ 0.94** โดย p95 ≤ 0.72 วินาที · **bge-m3 แม่นใกล้กันแต่ p95 ถึง 13 วินาที** เกิน timeout router → retrieval 10 วินาที (CONTRACT §0) ใช้บน CPU ไม่ได้
- **`MIN_VECTOR_SCORE` คงไว้ที่ 0.0** — hybrid ไม่เคยตอบ `chunks: []` ให้คำถามนอกคลังเลยที่ทุกค่า เพราะ BM25 ยังเจอคำร่วมอยู่เสมอ ตั้ง 0.30 ตัดฝั่ง vector ของคำถามนอกคลังได้แค่ 10% แต่ทิ้ง hit ที่ถูกไป 3% · คำถามนอกคลังจึงต้องให้ router (intent) และ generation (ตอบว่าไม่มีข้อมูล) จัดการ

| MIN_VECTOR_SCORE | hit ที่ถูกโดนตัด | นอกคลังได้ว่าง (vector) | นอกคลังได้ว่าง (hybrid) |
|---|---|---|---|
| 0.00 | 0.0% | 0% | 0% |
| 0.30 | 3.0% | 10% | 0% |
| 0.50 | 5.6% | 60% | 0% |
| 0.60 | 10.3% | 90% | 0% |

## จุดที่ควรรู้

- **SQLite คือแหล่งจริง** FAISS + BM25 เป็น snapshot ในหน่วยความจำที่สร้างจากชุด chunk เดียวกัน แล้วสลับทีเดียว `/search` ไม่เคยเห็น index ครึ่ง ๆ
- **05 ไม่ผ่อน filter เอง** ไม่เจอ = `200` + `chunks: []` การค้นซ้ำโดยตัด matchweek เป็นของ router (§3)
- **filter ที่ไม่รู้จัก → 422** เพื่อไม่ให้ filter ที่พิมพ์ผิดคืนผลแบบไม่กรอง
- **`data/team_aliases.json` เป็นไฟล์สำรอง** ตัวจริงเป็นของ 07 (PR ② จะดึงจาก `GET /football/teams`)
