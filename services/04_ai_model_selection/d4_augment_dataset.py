"""
D4 — ปรับ dataset จากคำที่ classifier พลาดบน routing cases

ที่มา: ยังไม่ได้รับ tests/routing_cases.jsonl ของจริงจาก member2 (40 เคส)
       จึงใช้ tests/simulated_routing_cases.jsonl (24 เคสที่เราเขียนเอง จำลองสไตล์คำถามจริง)
       รัน `python train.py` แล้วดู error log ได้ 8/24 เคสที่พลาด (accuracy 0.667) แบ่งเป็น 4 กลุ่มปัญหา:

  1. match_result / fixture_schedule ที่ใช้ชื่อเล่น "ยูไนเต็ด" (แมนยู) — dataset เดิมมีแต่ "ผี"/"แมนยู"
     ไม่เคยเห็น "ยูไนเต็ด" เลย → โมเดลไม่รู้จัก token นี้เกาะกับ intent ไหน
  2. weekly_summary ที่พูดว่า "เมื่อคืน...ทุกคู่" — dataset เดิมเน้นคำว่า "สัปดาห์นี้/แมตช์วีค" อย่างเดียว
     พอมีคำว่า "เมื่อคืน" (ซึ่ง match_result ก็ใช้บ่อย) โมเดลเทไป match_result
  3. trivia_history ที่ถามข้อเท็จจริงเชิงสถิติสะสม ("เคยไม่แพ้กี่นัดติด", "ตกรอบยูฟ่าปีไหน")
     ต่างจาก standings_stats (สถิติ "ฤดูกาลนี้/ตอนนี้") — โมเดลแยกสองอย่างนี้ไม่ค่อยออก
  4. standings_stats แบบภาษาอังกฤษที่ถามเปรียบเทียบ 2 ทีม ("who has more clean sheets X or Y")
     dataset เดิมมีตัวอย่างอังกฤษของ standings_stats แต่ไม่มีรูปแบบ "compare A vs B" เลย

ทางแก้: เพิ่มตัวอย่างที่ตรงกับ pattern ที่พลาดจริง (ไม่ใช่สุ่มเพิ่มทั่วไป) แล้วเทรนใหม่
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "intents.csv"

NEW_ROWS = [
    # 1) ชื่อเล่น "ยูไนเต็ด" สำหรับแมนยู — match_result / fixture_schedule
    ("ยูไนเต็ดชนะไปกี่ลูกเมื่อคืน", "match_result", "th"),
    ("ยูไนเต็ดแพ้หรือชนะนัดล่าสุด", "match_result", "th"),
    ("ยูไนเต็ดเจอใครนัดหน้า", "fixture_schedule", "th"),
    ("ยูไนเต็ดมีนัดกับใครสัปดาห์นี้", "fixture_schedule", "th"),
    # 2) weekly_summary แบบ "เมื่อคืน...ทุกคู่" ให้ต่างจาก match_result เดี่ยว ๆ
    ("สรุปเกมเมื่อคืนให้หน่อยทุกคู่เลย", "weekly_summary", "th"),
    ("เมื่อคืนแข่งกี่คู่ สรุปผลให้หน่อยทั้งหมด", "weekly_summary", "th"),
    ("คืนนี้มีกี่แมตช์ สรุปทุกคู่หลังจบเกมให้หน่อย", "weekly_summary", "th"),
    # 3) trivia_history เชิงสถิติสะสม/ประวัติ ให้ต่างจาก standings_stats (สถิติฤดูกาลนี้)
    ("สิงห์บลูตกรอบยูฟ่าแชมเปียนส์ลีกปีล่าสุดตอนไหน", "trivia_history", "th"),
    ("ปืนใหญ่เคยไม่แพ้ติดต่อกันกี่นัดในประวัติศาสตร์สโมสร", "trivia_history", "th"),
    ("อาร์เซนอลเคยได้แชมป์พรีเมียร์ลีกกี่สมัยรวมทั้งหมด", "trivia_history", "th"),
    ("ทีมไหนเคยครองสถิติไม่แพ้ยาวนานที่สุดในพรีเมียร์ลีก", "trivia_history", "th"),
    # 4) standings_stats ภาษาอังกฤษแบบเปรียบเทียบสองทีม
    ("who has more clean sheets city or arsenal", "standings_stats", "en"),
    ("how many clean sheets does arsenal have this season", "standings_stats", "en"),
    ("does city or liverpool have more points right now", "standings_stats", "en"),
]


def main():
    with open(DATA_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for text, intent, lang in NEW_ROWS:
            w.writerow([text, intent, lang])
    print(f"เพิ่ม {len(NEW_ROWS)} แถวเข้า {DATA_PATH}")


if __name__ == "__main__":
    main()
