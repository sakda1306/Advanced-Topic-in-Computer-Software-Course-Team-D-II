# D5 — เทียบ 3 วิธีจำแนก intent

held-out test set เดียวกัน: 51 ตัวอย่าง (20% ของ `data/intents.csv`, 203 ใช้เทรน)

| วิธี | accuracy | ต้องเทรนก่อนไหม | เร็ว/ถูกแค่ไหน | ต้องมีเน็ต/API key ไหม |
|---|---|---|---|---|
| TF-IDF (char n-gram) + LogisticRegression | 0.804 | ต้อง (เทรนทั้งชุด 99ms) | เร็วมาก รันในเครื่องได้ ไม่มีค่าใช้จ่าย | ไม่ต้อง |
| sentence-transformers embeddings + LogisticRegression | ยังไม่ได้รัน (รันไม่สำเร็จ: No module named 'sentence_transformers') | ต้อง | ปานกลาง (โหลดโมเดล ~470MB ครั้งแรก) | ต้องต่อ huggingface.co ตอนโหลดโมเดลครั้งแรก |
| ถาม LLM ตรง ๆ (few-shot ผ่าน Groq/Gemini) | ยังไม่ได้รัน (รันไม่สำเร็จ: groq: Host not in allowlist: api.groq.com. Add this host to your network egress settings to allow access. | gemini: Host not in allowlist: generativelanguage.googleapis.com. Add this host to your network egress settings to allow access.) | ไม่ต้อง | ช้าสุด + มีค่าใช้จ่าย/นัด (เรียก API ทุกครั้ง) | ต้องมี `GROQ_API_KEY`/`GEMINI_API_KEY` |

## สรุปเบื้องต้น (จากตัวเลขที่มี ณ ตอนนี้)

- TF-IDF ใช้งานจริงตอนนี้: 80.4% บน held-out split, เร็ว, ไม่มีค่าใช้จ่าย ไม่พึ่งเน็ต
  → เหมาะเป็น production classifier ของ `/local/classify` (ตามที่ contract กำหนด `tfidf-logreg-v1`)
- embeddings และ LLM-based ยังไม่มีตัวเลขจริงจากสภาพแวดล้อมที่เขียนไฟล์นี้ (ดูเหตุผลบนสุดของ
  `eval/compare_methods.py`) — รันสคริปต์นี้ในเครื่องที่ต่อเน็ตได้เพื่อเติมให้ครบ
- แม้ embeddings/LLM จะแม่นกว่า TF-IDF จริง ทั้งสองวิธีก็ช้ากว่าและมีต้นทุนต่อ request สูงกว่ามาก
  ซึ่งขัดกับเป้าหมายของ `/local/classify` ที่ต้องเป็น "ชั้นกรองที่เร็วและถูก" ก่อนค่อยเรียก LLM
  (ดู 03_process.txt เดิม: "ควบคุมต้นทุน General AI ด้วย token budget") — TF-IDF จึงน่าจะเป็นตัวเลือก
  ที่เหมาะกับงานนี้อยู่ดี แม้ accuracy จะไม่สูงสุดในสามวิธี
