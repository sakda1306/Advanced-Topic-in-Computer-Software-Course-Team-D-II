# ผลทดสอบงาน 01 Web App

วันที่ตรวจ: 26 กันยายน 2026

## ขอบเขตการเปลี่ยนแปลง

แก้ไขเฉพาะ `services/01_web_app` รวมหน้า Login, Chat, Football, Admin, มาสคอส 5 ทีม, API proxy, Docker และชุดทดสอบ ไม่มีการแก้ไข source ของทีมอื่น Docker integration อ่าน source ของทีม 02 เพื่อสร้าง image API สำหรับทดสอบ

## ผลตรวจ

| คำสั่ง | ผล |
| --- | --- |
| `pnpm test` | ผ่าน 25 tests ใน 9 files หลังปรับ Club Edition |
| `pnpm typecheck` | ผ่าน |
| `pnpm format:check` | ผ่าน |
| `docker compose build web` | ผ่าน production build; การตรวจรอบสุดท้ายใช้ build cache |
| `docker compose up -d --wait` | เริ่มระบบสำเร็จ |
| `docker compose up -d --no-deps --force-recreate --wait web` | สร้างเว็บ container ใหม่จาก image ล่าสุด และ health check ผ่าน |
| `pnpm test:smoke` | ผ่าน 23 integration checks |
| `node scripts/smoke.mjs --outage` ขณะหยุด API | ผ่าน 1 check: 502 Problem JSON และ request ID (ทดสอบในรอบก่อนหน้า) |
| `python scripts/validate-mascots.py` | ผ่าน atlas ทั้ง 5 ทีม (ทดสอบในรอบก่อนหน้า) |
| `git diff --check` | ผ่าน ไม่มี whitespace errors |

## สิ่งที่ชุดทดสอบครอบคลุม

- ล้างข้อมูลเมื่อ logout, cookie หมดอายุ หรือเปลี่ยนบัญชี; ป้องกันคำตอบค้างจากบัญชีเก่า
- โหลด session/history, ส่งข้อความต่อใน session เดิม, เก็บ draft เมื่อส่งล้มเหลว
- บันทึกทีมก่อนเปลี่ยนบริบทและเติมคำถามตัวอย่างลงช่องพิมพ์
- Markdown, citation ที่ตรงกับ source, ป้องกัน HTML และ URL ที่ไม่ปลอดภัย
- Feedback retry เฉพาะกรณี message ยังไม่พร้อม และจำกัดจำนวนครั้ง
- API proxy ส่ง cookie/request ID และแยก 502, 504, 429
- มาสคอสใช้งานด้วยคีย์บอร์ดและจำกัดตำแหน่งให้อยู่ใน viewport
- Football filters, รายงานว่าง และข้อมูล match ที่เป็น null
- Club Edition: เลือกแมตช์ถัดไปของทีมที่ถูกต้อง และเรียงอันดับใน League Snapshot
- Admin permissions, job polling, ยืนยันการเปลี่ยนแปลง, ป้องกันการเผยแพร่ร่างที่ยังไม่บันทึก
- HTTP ผ่าน Docker: 11 page routes, mascot assets, login/logout, favorite team, chat/history/feedback, football, admin statistics, pipeline, reports, logs/audit, users และ KB
- จงใจจำลอง router ล้มเหลวและ timeout เพื่อยืนยัน HTTP 502/504

## สภาพแวดล้อมและข้อจำกัด

- เว็บเปิดที่ <http://localhost:3000> ใช้ production image ของ Next.js
- API Backend ของทีม 02, PostgreSQL และ Redis ทำงานจริงใน Docker
- Router และ Football Data ใช้ stub ของทีม 02: ผลนี้ยังไม่ยืนยันการเชื่อม AI, Retrieval, Generation และข้อมูลฟุตบอลจริงของทุกทีม
- Unit/component tests ใช้ jsdom; ยังไม่ได้ตรวจภาพและ responsive layout ด้วย browser จริง
- Smoke test เพิ่มข้อมูล demo เช่น chat, feedback และ audit และเปลี่ยนสถานะรายงานใน stub ควรใช้กับชุด Docker สาธิตนี้
- Reindex ตรวจเพียงการรับคำขอและ job ID ไม่ได้ยืนยันการสร้างดัชนีจริงเสร็จสมบูรณ์

ดูวิธีเริ่มระบบ บัญชีสาธิต และคำสั่งทดสอบซ้ำใน [README.md](README.md)
