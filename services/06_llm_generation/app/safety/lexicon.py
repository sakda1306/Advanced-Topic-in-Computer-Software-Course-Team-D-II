"""คำศัพท์ไทย+อังกฤษสำหรับตรวจ safety — ปรับเพิ่มได้ตามผลทดสอบจริง"""

# ชั้น pre-check บน query: คำขอทีเด็ด/สูตรบอล/ราคาต่อรอง/แทงบอล
GAMBLING_REQUEST_PATTERNS = [
    r"ทีเด็ด",
    r"สูตรบอล",
    r"ราคาต่อรอง",
    r"อัตราต่อรอง",
    r"แทงบอล",
    r"แนะนำ.{0,10}เดิมพัน",
    r"เว็บพนัน",
    r"parlay",
    r"who should i bet",
    r"odds today",
    r"betting tips?",
    r"handicap.{0,10}(วันนี้|ราคา)",
]

# ชั้น post-check บน answer: คำแนะนำเดิมพัน
GAMBLING_TIPS_PATTERNS = [
    r"ควรแทง",
    r"ทีเด็ด",
    r"bet on\s",
    r"แนะนำให้ซื้อ",
    r"แนะนำให้แทง",
    r"i recommend betting",
]

# การโปรโมต/ชวนเล่นพนัน
GAMBLING_PROMOTION_PATTERNS = [
    r"สมัคร(สมาชิก)?.{0,10}(พนัน|เว็บ)",
    r"ฝากถอน",
    r"โบนัส.{0,10}(100%|เครดิต)",
    r"เว็บพนันออนไลน์",
]

# odds/handicap ตัวเลขที่ดูเหมือนราคาต่อรอง (ตรวจแยกกับ numeric guard)
GAMBLING_ODDS_PATTERN = r"\b\d{1,5}\s*/\s*\d{1,5}\b|\bhandicap\s*[-+]?\d+(\.\d+)?\b|ราคาต่อ\s*\d"

# canary token ถูกสร้างแบบสุ่มต่อ process ใน llm/client.py แล้วส่งเข้าที่นี่เพื่อตรวจ prompt leak
