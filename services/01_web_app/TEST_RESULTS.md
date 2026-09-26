# ผลทดสอบงาน 01 Web App

วันที่ตรวจ: 26 กันยายน 2026

## รอบล่าสุด — เตรียมรวมระบบตามรีวิว

ทดสอบการเปลี่ยนแปลงต่อจาก `a5df132` บน branch `feature/01-web-mekmai4234` และแก้เฉพาะ `services/01_web_app` ไม่มีการเพิ่ม workflow ส่วนกลางหรือแก้บริการของทีมอื่น

| รายการ | ผลรอบล่าสุด |
| --- | --- |
| `pnpm test` | ผ่าน Vitest 54 tests ใน 11 files และ Node test runner 5 tests รวม 59 tests |
| `pnpm typecheck` | ผ่าน |
| `pnpm format:check` | ผ่าน หลังจัดรูปแบบไฟล์ทดสอบ |
| `pnpm build` บน Windows / Node 24.19.0 | ผ่าน หลังแก้ปัญหา standalone symlink (`EPERM`); Windows ใช้ `pnpm start` |
| `docker compose build web` / Node 22 Alpine | ผ่าน รวม frozen-lockfile install และ production standalone build; ทดสอบซ้ำหลังแก้ config Windows |
| `docker compose up -d --wait api` | API, PostgreSQL, Redis และ stub services เริ่มทำงานได้ |
| `docker compose up -d --no-deps --force-recreate --wait web` | เว็บ image ที่แก้ UI เริ่มทำงานและ healthy |
| `pnpm test:smoke` | ผ่าน 23 checks รวม router failure 502 และ intentional timeout 504 |
| Browser จริง | Login/logout ด้วย demo1 และ admin; เปลี่ยน 5 ทีมบนมือถือ; แชทความรู้ทั่วไปแสดงคำอธิบายใหม่; citation โฟกัส source ถูกต้อง; Admin Dashboard และ KB โหลดข้อมูลได้ |
| Responsive spot checks | Login/Chat/Admin ที่ 390×844 และ Chat/Admin ที่ 1440×900; หน้าที่วัด document width ไม่ล้น viewport; ไม่ใช่การตรวจทุกหน้าทุก breakpoint |

การแก้ไขรอบนี้เพิ่มข้อความแยก retrieval ว่าง/ไม่พร้อม, คำตอบไม่มี sources และ general knowledge โดยคงข้อความ API เดิม; รองรับ error `INDEX_NOT_READY`/`RETRIEVAL_UNAVAILABLE`; เพิ่ม regression tests ของ sources/timestamps/KB acceptance/recovery; เพิ่ม `pnpm check`, HTTP integration runner และเอกสาร `INTEGRATION.md`

ข้อจำกัดของผลรอบนี้:

- Docker ใช้ API 02 + PostgreSQL/Redis จริง แต่ Router/Football Data ยังเป็น stub ของ 02; คำตอบและผลฟุตบอลใน browser เป็นข้อมูลสาธิต
- 5 tests ของ integration runner ใช้ข้อมูลสังเคราะห์เพื่อตรวจว่าตัวตรวจจับข้อผิดพลาดได้ ไม่ใช่ผล `test:integration` ต่อ 03–07 จริง
- ยังไม่ได้รัน `pnpm test:integration` กับ Compose กลาง เพราะยังไม่มีบริการครบและชุดข้อมูลจริงที่ยืนยันสำหรับ expected facts
- `INDEX_NOT_READY` ตรวจด้วย component/proxy tests; API 02 ปัจจุบันแปลงเป็น `RETRIEVAL_UNAVAILABLE` จึงไม่อ้างว่ารหัส 503 ผ่านบริการจริงครบเส้นทางแล้ว
- UI ไม่ได้บังคับ database-only หรือพิสูจน์ความจริงจากการมี citation; นโยบาย Router/Generation ยังต้องตกลงกับทีม
- Smoke เพิ่ม chat/feedback/audit และเปลี่ยนสถานะข้อมูลสาธิตตามขอบเขต script เดิม; browser ทดสอบด้วยบัญชีสาธิตและออกจากระบบหลังตรวจ
- ยังไม่มี CI check run บน GitHub: รอบนี้เตรียมคำสั่งในงาน 01 เท่านั้น เจ้าของ Deploy ยังต้องเพิ่ม workflow

## ผลรอบก่อนหน้า — ก่อนเตรียม integration

## ขอบเขตการเปลี่ยนแปลง

แก้ไขเฉพาะ `services/01_web_app` รวมหน้า Login, Chat, Football, Admin, มาสคอส 5 ทีม, API proxy, Docker และชุดทดสอบ ไม่มีการแก้ไข source ของทีมอื่น Docker integration อ่าน source ของทีม 02 เพื่อสร้าง image API สำหรับทดสอบ

## ผลตรวจ

| คำสั่ง | ผล |
| --- | --- |
| `pnpm test` | ผ่าน 41 tests ใน 10 files หลังแก้ account/history/team/match regressions |
| `pnpm typecheck` | ผ่าน |
| `pnpm format:check` | ผ่าน |
| `docker compose build web` | ผ่าน production build |
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
- Logout/Login: รอ Logout จบก่อนส่ง Login และรวมการกด Logout ซ้ำเป็นคำขอเดียว ทดสอบ success, 502, 504 และ network failure; หน้า Login ปิดปุ่มและแสดงสถานะระหว่างรอ
- History: ล้าง session ที่ตอบ 404; บล็อกการส่งเมื่อโหลดล้มเหลวชั่วคราวและเปิดให้ลองใหม่; คำตอบ history เก่าไม่เขียนทับแชทใหม่
- Team preference: บันทึกไม่สำเร็จยังคงทีมและบทสนทนาเดิม; ข้อผิดพลาดแสดงบนหน้าแรก, Football และ Admin แม้ไม่มีมาสคอสเปิดอยู่
- Match preview: LIVE มาก่อน SCHEDULED ในอนาคต แล้วจึง FINISHED ล่าสุด; ข้าม POSTPONED, CANCELLED และวันที่ไม่ถูกต้อง
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
