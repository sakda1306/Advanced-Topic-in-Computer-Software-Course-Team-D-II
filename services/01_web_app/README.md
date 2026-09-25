# PitchSide Web App

หน้าเว็บพรีเมียร์ลีกพร้อมธีม 5 ทีมและมาสคอสแบบลากได้สำหรับ Manchester United, Manchester City, Chelsea และ Arsenal มาสคอสเปิดแชทที่เชื่อมกับ `/api/chat` ของ backend ทีม Liverpool ยังไม่มีไฟล์ sprite จึงแสดงปุ่มแชทชั่วคราว

## เริ่มใช้งาน

1. เปิด backend ที่ `http://localhost:8000` หรือกำหนด `API_INTERNAL_URL` ใน `.env.local`
2. ที่โฟลเดอร์นี้ รัน `pnpm install` และ `pnpm dev`
3. เปิด `http://localhost:3000` และเข้าสู่ระบบด้วยบัญชีของ backend

มาสคอสใช้ sprite atlas WebP ขนาด 1536 × 2288 พิกเซล (8 คอลัมน์ × 11 แถว) จาก `D:\RMUTT\Advanced Ai\mascot` ซึ่งคัดลอกไว้ใน `public/mascots` แล้ว เปลี่ยนทีมจากแถบด้านบนเพื่อเปลี่ยนสีและมาสคอส ลากด้วยเมาส์หรือสัมผัสเพื่อย้ายตำแหน่ง ใช้ปุ่มลูกศรเมื่อโฟกัสมาสคอสเพื่อย้ายด้วยคีย์บอร์ด ตำแหน่งบันทึกใน browser localStorage

เมื่อ Liverpool มี sprite atlas ให้คัดลอกไฟล์ไปที่ `public/mascots/liverpool.webp` แล้วกำหนด `mascot` ของ Liverpool ใน `lib/teams.ts` เป็น `/mascots/liverpool.webp`
