"""
D5 (Could) — คณิตศาสตร์ของ Poisson model สำหรับทำนายผลนัด

**ทำไมยังต่อกับ 07 จริงไม่ได้ตอนนี้ (ดู README หัวข้อ "ทำไม /local/predict ตอบ 501")**
ฟังก์ชันในไฟล์นี้เป็น "pure function" ล้วน ๆ ไม่พึ่งข้อมูลจากที่ไหน — รับค่าเฉลี่ยประตูมาแล้วคำนวณ
ความน่าจะเป็นแพ้/ชนะ/เสมอ ทดสอบได้เต็มที่โดยไม่ต้องมี service 07 หรือฐานข้อมูลจริง
เมื่อ 07 มีข้อมูลจริงแล้ว งานที่เหลือคือแค่เขียนฟังก์ชันดึง "ค่าเฉลี่ยประตูได้/เสีย" มาป้อนให้ฟังก์ชันนี้
"""
import math
from dataclasses import dataclass

# ค่าเฉลี่ยประตูต่อนัดของพรีเมียร์ลีกโดยรวม (baseline) ใช้ตอนทีมใดทีมหนึ่งไม่มีข้อมูลพอ
LEAGUE_AVG_GOALS_PER_MATCH = 1.35

# แต้มต่อความได้เปรียบเจ้าบ้าน (home advantage) แบบคูณเข้ากับ expected goals ของทีมเหย้า
HOME_ADVANTAGE_FACTOR = 1.15

MAX_GOALS = 8  # ตัดหางการแจกแจงที่ N ประตู (ความน่าจะเป็นเกิน 8-0 ต่ำมากจนไม่มีนัยสำคัญ)


@dataclass
class TeamStrength:
    """สรุปฟอร์มของทีมจากผลนัดล่าสุด (จะมาจาก 07 ในอนาคต)"""

    attack_goals_per_match: float  # ยิงได้เฉลี่ยกี่ลูกต่อนัด
    defense_goals_conceded_per_match: float  # เสียเฉลี่ยกี่ลูกต่อนัด
    matches_used: int


def _poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) เมื่อ X ~ Poisson(lam)"""
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def expected_goals(
    attacking: TeamStrength, defending: TeamStrength, is_home: bool
) -> float:
    """
    Expected goals ของทีมหนึ่ง = เฉลี่ยระหว่าง "ทีมนี้ยิงเก่งแค่ไหน" กับ "ทีมตรงข้ามเสียง่ายแค่ไหน"
    เทียบกับค่าเฉลี่ยลีก แล้วคูณ home advantage ถ้าเป็นทีมเหย้า
    """
    attack_strength = attacking.attack_goals_per_match / LEAGUE_AVG_GOALS_PER_MATCH
    defense_weakness = defending.defense_goals_conceded_per_match / LEAGUE_AVG_GOALS_PER_MATCH
    xg = attack_strength * defense_weakness * LEAGUE_AVG_GOALS_PER_MATCH
    if is_home:
        xg *= HOME_ADVANTAGE_FACTOR
    return max(xg, 0.05)  # กันค่าติดลบ/ศูนย์ที่ทำให้ Poisson พัง


def match_outcome_probabilities(
    home: TeamStrength, away: TeamStrength
) -> dict:
    """
    คำนวณ P(home win), P(draw), P(away win) ด้วย Independent Poisson model:
    สมมติจำนวนประตูของสองทีมเป็นอิสระต่อกัน แจกแจงแบบ Poisson แยกกัน
    แจกแจงร่วม = คูณกัน แล้วรวมตามเงื่อนไขบ้าน > เยือน / เท่ากัน / บ้าน < เยือน
    """
    home_xg = expected_goals(home, away, is_home=True)
    away_xg = expected_goals(away, home, is_home=False)

    home_win = draw = away_win = 0.0
    for h in range(MAX_GOALS + 1):
        p_h = _poisson_pmf(h, home_xg)
        for a in range(MAX_GOALS + 1):
            p_a = _poisson_pmf(a, away_xg)
            joint = p_h * p_a
            if h > a:
                home_win += joint
            elif h == a:
                draw += joint
            else:
                away_win += joint

    total = home_win + draw + away_win  # ควรใกล้ 1.0 อยู่แล้ว แต่ normalize กันหางที่ตัดทิ้งไป
    return {
        "home_win": round(home_win / total, 4),
        "draw": round(draw / total, 4),
        "away_win": round(away_win / total, 4),
        "home_xg": round(home_xg, 3),
        "away_xg": round(away_xg, 3),
    }
