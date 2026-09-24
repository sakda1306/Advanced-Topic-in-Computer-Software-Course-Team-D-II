# Team D-II — DL-06: Agentic AI System I · ผู้ช่วยฟุตบอล (Football Assistant)

โปรเจกต์กลุ่มวิชา Advanced Topics in Computer Software (04622404)

ผู้ช่วย AI ตอบคำถามเรื่องฟุตบอล Premier League — ความรู้ฟุตบอลพร้อมอ้างอิง ผลและโปรแกรมการแข่งขัน ตารางคะแนน และรายงานสรุปประจำสัปดาห์
พัฒนาต่อจากระบบ RAG (week4 / week5) และสถาปัตยกรรม API Backend ของ Travel Safety Assistant เดิมของทีม โดยเพิ่มข้อมูลจาก football-data.org และ API-Football

## เอกสาร — อ่านตามลำดับนี้

| ไฟล์ | เนื้อหา |
|---|---|
| [`docs/00_PLAN_OVERVIEW.md`](docs/00_PLAN_OVERVIEW.md) | แผนงาน สถาปัตยกรรม ตาราง service ขอบเขต |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | ข้อตกลง API ระหว่าง service |
| [`docs/GIT_FLOW.md`](docs/GIT_FLOW.md) | คู่มือใช้ git ของทีม — **อ่านก่อนเริ่มงาน** |
| [`docs/SCHEDULE.md`](docs/SCHEDULE.md) | ใครทำอะไร วันไหน |
| [`DL-06-Agentic-AI-System-I/`](DL-06-Agentic-AI-System-I/) | แผนต้นฉบับของอาจารย์ (8 โมดูล) |

## Branch

```
main      ← เวอร์ชันนำเสนอ · merge จาก develop เท่านั้น
develop   ← default branch · จุดรวมงาน · เข้าได้ผ่าน PR เท่านั้น
feature/<เลข>-<โมดูล>-<github-username>   ← branch ของแต่ละคน
```

## สถานะ

ขั้นออกแบบ — ยังไม่มีโค้ด · service จะอยู่ใน `services/` และรันทั้งระบบด้วย `make up` (Docker Compose)
