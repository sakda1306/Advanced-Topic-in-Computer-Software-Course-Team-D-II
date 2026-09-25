# 05 Retrieval / Knowledge — แบบระบบ · `retrieval`

> เจ้าของ: sakda1306 · สถานะ: รอรีวิว · อ้างอิง: `00_PLAN_OVERVIEW.md` หัวข้อ 3, 7, 8 · `CONTRACT.md` §0, §4, §6 · `SCHEDULE.md` หัวข้อ 05
> เอกสารนี้บอกว่า 05 ทำอะไร และตัดสินใจอะไรไปแล้วพร้อมเหตุผล ลำดับงานละเอียดอยู่ใน implementation plan แยกต่างหาก

---

## 1. เป้าหมายและขอบเขต

05 เป็นแกน RAG ของระบบ: เก็บ Knowledge Base (คลัง trivia + เอกสารข้อมูลสดจาก 07) และค้นแบบ hybrid (BM25 + FAISS + RRF) ให้ router ตามเส้น `football_rag` ยกแกนมาจาก RAG week4 และติดตัวแก้ปัญหาจาก week5 ข้อ 1, 2, 3, 5

| ผู้เรียก | ใช้อะไร | ตาม |
|---|---|---|
| 03 router | `POST /search` | CONTRACT §4 |
| 07 football-data | `POST /index/upsert`, `DELETE /index/{doc_id}` | CONTRACT §6 |
| 02 api (หน้า admin) | `GET /index/stats`, `POST /index/rebuild`, `GET /index/jobs/{job_id}` | CONTRACT §6 |

**ไม่ทำในรอบนี้**: แปลคำถามไทย → อังกฤษ (03 ทำ) · multi_query (ดูหัวข้อ 9) · เรียก LLM ใด ๆ (§8 จำกัดไว้ที่ 03, 04, 06) · Postgres / pgvector

### การตัดสินใจที่ล็อกแล้ว

| เรื่อง | เลือก | เหตุผล |
|---|---|---|
| ที่เก็บ index | SQLite เป็นแหล่งจริง + snapshot (FAISS + BM25) ในหน่วยความจำ สลับทีเดียว | BM25 กับ FAISS สร้างจากชุด chunk เดียวกันเสมอ จึงตรงกันโดยโครงสร้าง (§6) · ล่มกลางทางไม่เหลือไฟล์ครึ่ง ๆ · restart ไม่ต้อง embed ใหม่ |
| ชื่อเล่นทีม | ดึง `GET /football/teams` ของ 07 + cache 1 ชม. + ไฟล์สำรองใน 05 | แหล่งเดียวกับ router · ต้องแก้ CONTRACT §7 เพิ่ม retrieval เป็นผู้เรียก |
| reranker | **ปิดเป็นค่าเริ่มต้น** (`RERANK_MODEL` ว่าง) · แนะนำ `cross-encoder/ms-marco-MiniLM-L-6-v2` | eval PR ③: ms-marco hit@1 ต่ำสุด 0.939 ที่ p95 สูงสุด 613.7 ms ใน process บนโน้ตบุ๊ก · รีวิว #10: ตัวเลขมาจากเอกสารจำลองและเครื่องที่ไม่ใช่เครื่อง deploy จึงเปิดผ่าน env หลังวัดซ้ำ · bge-reranker-v2-m3 p95 ~14 s เกิน timeout 10 s |
| multi_query | ไม่ทำ | router เขียนคำถามใหม่ 1 แบบอยู่แล้ว + 05 ค้นสองภาษา + ขยายชื่อเล่น · ไม่เพิ่มฟิลด์ใน §4 |

---

## 2. โครงสร้าง service

```
services/05_retrieval_knowledge/
  app/
    main.py            create_app() + lifespan: เปิด SQLite → โหลดโมเดล → สร้าง snapshot แรก
    core/              config, errors + Problem-JSON, request id, logging (JSON)
    api/               middleware (X-Request-ID, body guard) · routes: health, search, index
    kb/
      store.py         SQLite: documents, chunks, meta
      chunking.py      trivia = 1 QA / chunk · เอกสารอื่นตัดที่ "## "
      trivia.py        parse football_trivia_qa.txt + ตัดข้อซ้ำ + ตัดข้อขัดแย้ง
      doc_ids.py       ตรวจรูปแบบ doc_id ตาม category (§6)
    search/
      tokenize.py      จาก week4 (อังกฤษ + ไทยด้วย pythainlp)
      embedder.py      หุ้ม sentence-transformers (เทสใช้ FakeEmbedder)
      reranker.py      หุ้ม CrossEncoder · ปิดได้
      snapshot.py      FAISS + BM25 + metadata ของ chunk · ค้นแบบมี filter
      hybrid.py        โหมด bm25 / vector / hybrid + RRF
      aliases.py       ชื่อเล่นทีม: 07 → cache → ไฟล์สำรอง
    index/service.py   upsert / delete / rebuild · lock · สลับ snapshot · jobs
  scripts/             entrypoint.sh · ingest_trivia.py · eval_retrieval.py · smoke.py
  data/                football_trivia_qa.txt · team_aliases.json (สำรอง)
  tests/
```

**ข้อบังคับ**
- **uvicorn worker เดียวเท่านั้น** — index อยู่ในหน่วยความจำของ process ถ้าหลาย worker แต่ละตัวจะถือ index คนละชุดหลัง upsert
- งานกิน CPU (embed, FAISS, สร้าง BM25, rerank) รันใน threadpool ไม่บล็อก event loop
- error / request id / logging ใช้แบบเดียวกับ 02 (Problem-JSON ตาม §0, `service: "retrieval"`) — โค้ดซ้ำกันได้เพราะแยก container
- embedding model: `paraphrase-multilingual-MiniLM-L12-v2` (week4) อ่านจาก env · cache โมเดลใน volume `HF_HOME`
- ไฟล์ golden อยู่ที่ `eval/` ของ root ตามแผนหัวข้อ 8 · สคริปต์วัดผลอยู่ใน 05

---

## 3. ข้อมูลและการ ingest

### 3.1 SQLite (`KB_DB_PATH`, WAL mode)

| ตาราง | ฟิลด์ | หมายเหตุ |
|---|---|---|
| `documents` | `doc_id` PK · `title` · `category` · `origin` · `season` · `matchweek` · `team_ids` (JSON) · `date` · `fetched_at` · `url` · `topic` · `text` · `content_hash` · `updated_at` | 1 แถวต่อ doc_id |
| `chunks` | `chunk_id` PK (`<doc_id>#c<N>`) · `doc_id` FK ลบตามกัน · `ord` · `text` · `bm25_text` · `embedding` (float32 blob) | |
| `meta` | `index_version` · `embedding_model` | ชื่อโมเดลใน env ไม่ตรงกับที่บันทึก → embed ใหม่ทั้งหมดตอนเริ่ม |

### 3.2 การตัด chunk (week5 #3 — ไม่ตัดตามจำนวนตัวอักษร)

- `trivia`: 1 chunk = `Q: …\nA: …` · `bm25_text` = คำถาม 2 ครั้ง + คำตอบ (แบบ week4)
- อื่น ๆ: ตัดที่บรรทัดขึ้นต้น `## ` · ข้อความก่อนหัวข้อแรก = `c0` · ทุก chunk ขึ้นต้นด้วย `title` ของเอกสาร
- ข้อจำกัด: MiniLM อ่านได้ราว 128 token — chunk ยาวถูกตัดท้ายฝั่ง vector (BM25 ยังเห็นครบ) 07 จึงควรแบ่งหัวข้อด้วย `## `

### 3.3 คลัง trivia (week5 #2)

- `doc_id` = `trivia-NNNN` จากลำดับข้อในไฟล์ต้นฉบับ (0001–1996) · ไม่เปลี่ยนแม้ตัดข้อซ้ำ
- ทำความสะอาด: ตัดช่องว่างหัวท้าย · ยุบช่องว่างซ้ำ
- เทียบคำถามด้วยข้อความที่ normalize แล้ว (ตัวพิมพ์เล็ก · ไม่มีเครื่องหมายวรรคตอน · ไม่มีเครื่องหมายเหนืออักษร) · เทียบคำตอบแบบเดียวกันและไม่สนลำดับคำ ("Petr Cech" = "Petr Čech") · คลังจริง: 1,996 ข้อ → ข้อซ้ำ 39 · ข้อขัดแย้ง 2 กลุ่ม (523/1839, 1804/1838) → 1,953 เอกสาร
  - คำถามซ้ำ + คำตอบเดียวกัน → เก็บข้อแรก
  - คำถามซ้ำ + คำตอบต่างกัน (ขัดแย้ง) → **ตัดทั้งกลุ่ม** · log รายงานจำนวนและ id ที่ตัด
- metadata: `category: "trivia"` · `origin: "kb"` · `season` / `matchweek` / `fetched_at` = null · `team_ids: []` · `title` = คำถาม (≤ 120 ตัวอักษร) · `topic` = หมวดเดิม (World Cup, Ballon d'Or, …) เป็นฟิลด์เสริมแบบ optional ตาม §0
- `entrypoint.sh` รัน ingest ทุกครั้งที่เริ่ม · เอกสารที่ `content_hash` ไม่เปลี่ยนถูกข้าม จึงรันซ้ำได้

---

## 4. การค้นหา — `POST /search` (§4)

**รับ**: `query` (ไม่ว่าง ≤ 1000 ตัวอักษร) · `query_original` (ไม่ส่ง = ใช้ `query`) · `top_k` 1–20 (ค่าเริ่มต้น 5) · `filters` · `mode` (`hybrid` ค่าเริ่มต้น | `bm25` | `vector`) · snapshot ยังไม่พร้อม → 503 `INDEX_NOT_READY`

1. **ขยายคำค้นด้วยชื่อเล่น (week5 #1)** — หาชื่อเล่นใน `query` และ `query_original` แล้วต่อชื่อทางการท้ายคำค้นฝั่ง BM25 · จับชื่อยาวสุดก่อน · ชื่ออังกฤษต้องตรงทั้งคำ · ชื่อไทยต้องตรงกับลำดับคำที่ตัดด้วย pythainlp ทั้งคำ ("ผี" ต้องไม่จับ "ผีเสื้อ" · "แมนยู" ถูกตัดเป็น แมน|ยู ทั้งใน alias และในประโยค จึงยังจับได้) · ไม่เพิ่ม `team_ids` ใน filter เอง
2. **กรอง metadata ก่อนค้น** — `category` อยู่ในรายการ · `season` / `matchweek` ตรง · `team_ids` มีตัวใดตัวหนึ่งตรง · `date_from` / `date_to` เทียบกับ `date` (เอกสารไม่มีวันที่ถูกตัดเมื่อมี filter วันที่) · ไม่เหลือ chunk → `200` + `chunks: []` · **05 ไม่ผ่อน filter เอง** (ลำดับถอยเป็นของ router §3)
3. **BM25** (hybrid, bm25) — คำค้นที่ขยายแล้ว · คะแนนเฉพาะ chunk ที่ผ่าน filter · เก็บ `CANDIDATE_K` อันดับที่คะแนน > 0
4. **vector** (hybrid, vector) — embed `query` (คำถามที่ router เขียนใหม่เป็นอังกฤษ) — เดิม embed `query_original` แต่ eval PR ③ พบว่าภาษาไทยทำชุด match hit@1 ตก (hybrid 0.70 → 0.90 เมื่อใช้ `query` · trivia เท่าเดิม) · FAISS ผ่าน `IDSelectorBatch` เฉพาะ chunk ที่ผ่าน filter · เก็บ `CANDIDATE_K` อันดับ (ตัดที่ `vector_score < MIN_VECTOR_SCORE` เมื่อค่ามากกว่า 0)
5. **รวม** — hybrid: `score` = RRF (`RRF_K` = 60) · โหมดเดี่ยว: `score` = คะแนนดิบของวิธีนั้น · เรียงมาก → น้อย
6. **rerank** (เมื่อตั้ง `RERANK_MODEL`) — ให้คะแนนผู้เข้ารอบ `CANDIDATE_K` อันดับด้วย `query` · ใส่ `rerank_score` แล้วเรียงตามนั้น · โหลดไม่ได้หรือล้ม → ใช้ผลข้อ 5 ต่อและเขียน log
7. **ตอบ** — ตัดเหลือ `top_k` · แต่ละ chunk: `chunk_id`, `text`, `score`, `bm25_score`, `vector_score` (null ถ้าวิธีนั้นไม่เจอ), `rerank_score`, `source` (Source ตาม §0 · `ref` = ลำดับ 1..n) · พร้อม `request_id`, `latency_ms`, `index_version`

**เป้าความเร็ว**: p95 ≤ 300 ms ที่ราว 5,000 chunk บน CPU เมื่อปิด rerank (งบ router → retrieval คือ 10 วินาที)

---

## 5. การจัดการ index (§6)

### `POST /index/upsert`
- ตรวจ: `category` / `origin` อยู่ใน enum · `doc_id` ตรงรูปแบบของ category ตามตาราง §6 · `text` ไม่ว่าง · ≤ 100 เอกสารต่อคำขอ · ผิด → 422 ทั้งคำขอ
- ทำทั้งคำขอเป็นก้อนเดียวใต้ lock: `content_hash` ไม่เปลี่ยน → ข้าม · ตัด chunk + embed เอกสารที่เปลี่ยน **ก่อนเขียน** → SQLite transaction เดียว (แทน chunk เดิมของ doc_id นั้นทั้งหมด) → สร้าง snapshot ใหม่ → สลับ → `index_version` = เวลาปัจจุบัน (+07:00)
- ขั้นไหนล้ม → 500 และไม่มีอะไรเปลี่ยน ทั้ง SQLite และ snapshot ที่ใช้ค้นอยู่
- ตอบ `{request_id, upserted, chunks, index_version}` · `upserted` = จำนวนเอกสารที่รับ (รวมที่ไม่เปลี่ยน) · ไม่มีอะไรเปลี่ยน → `index_version` เดิม

### `DELETE /index/{doc_id}` → `{deleted: true | false}` (200) · ใช้ lock เดียวกัน

### `GET /index/stats` → `{documents, chunks, by_category, index_version}`

### `POST /index/rebuild` + `GET /index/jobs/{job_id}`
- รับ `{request_id, category?}` → `202 {job_id}` · ทำใน background: ตัด chunk + embed ใหม่จากข้อความใน SQLite แล้วสลับทีเดียว · ระหว่างนั้น `/search` ใช้ index เดิม
- สั่งซ้ำขณะรันอยู่ → 409 `JOB_ALREADY_RUNNING`
- job อยู่ในหน่วยความจำ 50 รายการล่าสุด: `{job_id, status, started_at, finished_at, detail}` · restart แล้วหาย

### snapshot
- ก้อนที่ไม่ถูกแก้หลังสร้าง: FAISS (`IndexIDMap2` + `IndexFlatIP`) · BM25 · metadata ของ chunk · `index_version`
- `/search` อ่าน snapshot ปัจจุบันโดยไม่รอ lock
- snapshot ใหม่สร้างจาก embedding และ token ที่มีในหน่วยความจำอยู่แล้ว ไม่ embed ซ้ำ
- ไม่เขียน snapshot ลงดิสก์ — ตอนเริ่มระบบสร้างจาก SQLite (embedding ที่เก็บไว้)

### ชื่อเล่นทีม
- `GET /football/teams` ของ 07 · timeout 3 วินาที · cache `ALIASES_CACHE_SECONDS` (3600)
- ดึงไม่ได้ → `data/team_aliases.json` · พักไม่เรียก 07 เป็นเวลา 60 วินาที ไม่ให้ `/search` ช้า

### health
- `GET /health` → 200 ตาม §0 เสมอ
- `GET /ready` → 200 เมื่อ snapshot พร้อม ไม่งั้น 503 · ใช้เป็น healthcheck ของ compose

---

## 6. Error และ config

| code | status | เมื่อไร |
|---|---|---|
| `VALIDATION_ERROR` | 422 | ฟิลด์ผิด · doc_id ไม่ตรงรูปแบบ · ข้อความมีอักขระ NUL |
| `PAYLOAD_TOO_LARGE` | 413 | `/search` > 64 KB · `/index/upsert` > 5 MB |
| `NOT_FOUND` | 404 | ไม่มี job id |
| `JOB_ALREADY_RUNNING` | 409 | rebuild ซ้ำขณะรันอยู่ |
| `INDEX_NOT_READY` | 503 | index ยังไม่พร้อมตอนเริ่มระบบ (**code ใหม่ — เพิ่มใน CONTRACT**) |
| `INTERNAL_ERROR` | 500 | อื่น ๆ · ไม่เปิดเผยรายละเอียดภายใน |

| env | ค่าเริ่มต้น | หมายเหตุ |
|---|---|---|
| `KB_DB_PATH` | `/data/kb.sqlite` | อยู่ใน volume |
| `TRIVIA_FILE` | `data/football_trivia_qa.txt` | |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | เปลี่ยน = embed ใหม่ทั้งหมดตอนเริ่ม |
| `HF_HOME` | `/models` | cache โมเดล อยู่ใน volume |
| `RERANK_MODEL` | ว่าง | ว่าง = ปิด · แนะนำ `cross-encoder/ms-marco-MiniLM-L-6-v2` (อังกฤษ ให้คะแนนด้วย `query` · ~90 MB cache ใน `HF_HOME`) |
| `MIN_VECTOR_SCORE` | `0.0` | 0 = ปิด · MiniLM ให้ cosine ไทย-อังกฤษต่ำ (ราว 0.26) ค่าจริงมาจาก eval |
| `CANDIDATE_K` / `RRF_K` | `20` / `60` | |
| `FOOTBALL_DATA_URL` | `http://football-data:8000` | ใช้ดึงชื่อเล่นทีม |
| `ALIASES_CACHE_SECONDS` | `3600` | |
| `GIT_SHA` / `LOG_LEVEL` | `0.1.0` / `INFO` | |

---

## 7. การทดสอบ

- **unit**: parse trivia · ตัดข้อซ้ำ · ตัดข้อขัดแย้ง · ตัด chunk ที่ `## ` · รูปแบบ doc_id ทุก category · จับชื่อเล่น (ต้องไม่จับ "ผีเสื้อ") · filter ทุกแบบ · RRF · snapshot มีจำนวนใน FAISS = BM25 = chunk เสมอ
- **index**: embed ล้มกลางทาง → ไม่มีอะไรเปลี่ยน · hash เดิมไม่ embed ซ้ำ · delete แล้วค้นไม่เจอ · ค้นระหว่าง upsert ได้ผลจาก snapshot เดิมหรือใหม่อย่างใดอย่างหนึ่งครบทั้งชุด · rebuild + สถานะ job + 409
- **API**: รูปร่าง response ตาม §4 / §6 ทุก endpoint · error code ทุกตัว · Problem-JSON
- เทสส่วนใหญ่ใช้ **FakeEmbedder** (deterministic ไม่โหลด torch) · เทสกับโมเดลจริง mark แยก
- **CI** `.github/workflows/retrieval-05.yml`: job 1 ruff + pytest · job 2 ingest คลังจริงด้วยโมเดลจริง (cache `HF_HOME`) แล้วรัน `scripts/smoke.py` กับ `/search` และ `/index/*`

---

## 8. Eval (week5 #5) — `scripts/eval_retrieval.py`

- `eval/golden_trivia.jsonl` สร้างใหม่แก้ข้อบกพร่องที่ week5 พบ: 60 ข้อจริง · สัดส่วนหมวดตามคลัง · ครบ 4 แบบคำถาม (verbatim / slang / partial / natural) · แก้ตัวสร้างแบบ partial · map คำตอบเป็น `trivia-NNNN` ด้วยข้อความคำถาม (เลข chunk ของ week4 ไม่ตรงกับเลขข้อ)
- `eval/golden_match.jsonl` 20 ข้อ: ผลแข่ง · ตารางคะแนน · โปรแกรม · รายงานประจำสัปดาห์ พร้อม filter และ doc_id ที่ควรเจอ · ใช้ชุดเอกสารแช่แข็ง `eval/fixtures/live_docs.json` ให้ตัวเลขรันซ้ำได้
- คำถามนอกคลัง 10 ข้อ สำหรับปรับ `MIN_VECTOR_SCORE` ให้ได้ `chunks: []` เมื่อควร
- ตัวชี้วัด: hit@1 · hit@5 · MRR · latency p50 / p95 · เทียบ bm25 / vector / hybrid / hybrid+rerank (bge-reranker-v2-m3 และ ms-marco-MiniLM-L-6-v2)
- ผลออกเป็น JSON (member6 ใช้ทำ `eval/report.html`) + ตารางใน README
- **ผล (PR ③)** อยู่ใน README ของ 05 · สรุปการตัดสินใจจากตัวเลข:
  - `MIN_VECTOR_SCORE` = **0.0** ต่อไป: hybrid ไม่ได้ `chunks: []` กับคำถามนอกคลังที่ทุกค่า (BM25 เจอคำร่วมเสมอ) ค่าที่สูงขึ้นจึงไม่เปลี่ยนสิ่งที่ router ได้รับ → คำถามนอกคลังเป็นหน้าที่ของ router / generation
  - reranker: ms-marco-MiniLM-L-6-v2 ได้ hit@1 ต่ำสุด 0.939 ที่ p95 สูงสุด 613.7 ms (ใน process โมเดลอุ่นแล้ว ไม่รวม HTTP) · bge-reranker-v2-m3 p95 ~14 s เกิน timeout 10 s ใช้บน CPU ไม่ได้ · **ปิดเป็นค่าเริ่มต้น** (รีวิว #10) เปิดผ่าน `RERANK_MODEL` หลังวัดกับเอกสาร 07 จริง คำ rewrite ของ router จริง และเครื่อง deploy
  - คำถามที่ตอบไม่ได้: retrieval ไม่ว่างเองถ้า filter ยังเหลือเอกสาร · top `rerank_score` ของ ms-marco ≥ 4 แยกได้ (ปฏิเสธคำถามที่ตอบได้ 0.4% · ปล่อยคำถามที่ตอบไม่ได้ 0%) เสนอเป็นจุดตั้งต้นให้ router / generation — ชุดที่ตอบไม่ได้มีแค่ 20 ข้อ
  - ฝั่ง vector เปลี่ยนไป embed `query` แทน `query_original`: ชุด match hybrid hit@1 0.70 → 0.90 · MRR 0.82 → 0.95 · trivia เท่าเดิม · embed ทั้งสองแล้วรวม RRF ทำ trivia ตกเล็กน้อย จึงไม่ใช้ · ข้อควรรู้: คำอังกฤษใน golden เขียนมาดี ถ้า router แปลแย่ ผลจริงจะต่ำกว่านี้
  - `live_docs.json` เป็นข้อมูล**จำลอง** แทนด้วยเอกสารจริงจาก 07 เมื่อมี แล้วรันใหม่

---

## 9. การแบ่ง PR และงานที่พึ่งคนอื่น

| PR | เนื้อหา | ปลดล็อก | วัน |
|---|---|---|---|
| ① | โครง service · SQLite · ingest trivia · snapshot · `/search` ครบทุกโหมด + filter + ชื่อเล่นจากไฟล์ + rerank flag · `/health` · `/ready` · เทส · CI | 03, 06 | D3 |
| ② | `/index/upsert` · `DELETE /index/{doc_id}` · `/index/stats` · `/index/rebuild` · `/index/jobs/{job_id}` · ดึงชื่อเล่นจาก 07 | 07 | D4 |
| ③ | golden sets · eval script · ตัวเลขใน README | – | D5 |
| CONTRACT (แยก) | §7 เพิ่ม retrieval เป็นผู้เรียก `GET /football/teams` · §4 / §6 เพิ่ม `INDEX_NOT_READY` (503) | – | ก่อน PR ② |

ทุก PR เข้า `develop` ให้ member6 รีวิว (GIT_FLOW §2)

**ส่งต่อ member6** (เจ้าของ Dockerfile / compose): worker เดียว · volume `/data` และ `HF_HOME` · healthcheck `GET /ready` พร้อม `start_period` พอสำหรับโหลดโมเดล · ดาวน์โหลดโมเดลตอน build image ได้ถ้าต้องการให้เริ่มเร็ว · มีสองโมเดล: embedding (`EMBEDDING_MODEL`) และ reranker (`RERANK_MODEL`, ms-marco ~90 MB)

**ความเสี่ยง**
- image ใหญ่ (torch CPU + โมเดล) → ใช้ torch แบบ CPU-only และ cache โมเดลใน volume
- `MIN_VECTOR_SCORE` ผิดค่า → ตัดผลที่ควรเจอ หรือไม่เคยว่างเลย · ปรับจาก eval ใน D5 ก่อนเดโม
- 07 ส่งเอกสารไม่มี `## ` → chunk เดียวยาว ฝั่ง vector อ่านไม่ครบ · แจ้ง member5 ตั้งแต่ D4
