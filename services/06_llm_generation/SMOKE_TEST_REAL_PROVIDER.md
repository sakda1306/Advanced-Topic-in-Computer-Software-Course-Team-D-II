# หลักฐาน Smoke Test บน LLM Provider จริง — โมดูล 06

> เติมข้อมูลนี้หลังรันจริงอย่างน้อย 1 ครั้ง (ไม่ใช่ mock) แล้วแนบไฟล์นี้ใน PR #11
> อ้างอิงตาม `docs/CONTRACT.md` §8 (ต้องระบุ model, fallback, token usage)

## ข้อมูลการรัน

- วันที่/เวลา: __________
- ผู้รัน: __________
- Provider หลักที่ใช้: Groq (model: __________)
- Fallback ที่ตั้งไว้: Gemini (model: __________)
- `LLM_MOCK`: false
- Endpoint ที่ทดสอบ: [ ] `/generate` (grounded)  [ ] `/generate` (passthrough)  [ ] `/report/weekly`

## ผลลัพธ์

| เคส | Provider ที่ตอบจริง (หลัก/fallback) | เวลาที่ใช้ (s) | Token usage (prompt/completion) | ผ่าน deadline ไหม | หมายเหตุ |
|---|---|---|---|---|---|
| grounded ปกติ | | | | 22s budget | |
| grounded citation | | | | 22s budget | |
| grounded insufficient | | | | 22s budget | |
| passthrough แปลภาษา | | | | 22s budget | |
| report weekly (list lineups/statistics) | | | | 55s budget | |
| กรณี provider หลักล่ม (ทดสอบ fallback) | | | | - | |

## ข้อจำกัดที่พบระหว่างทดสอบจริง (ถ้ามี)

- __________

## สรุปสำหรับ reviewer

- [ ] ทดสอบครบตามตารางด้านบน
- [ ] ถ้าทดสอบไม่ครบ ระบุเหตุผล/ข้อจำกัดชัดเจนแทน (เช่น ไม่มี API key, quota หมด)
