"""
D3 — เทรน intent classifier: TF-IDF + LogisticRegression
รัน: python train.py

ทำ:
1. โหลด data/intents.csv (8 หมวด)
2. แบ่ง train/test แบบ stratified (80/20) เพื่อวัด accuracy บนข้อมูลของเราเอง
3. เทรนบน "ข้อมูลทั้งหมด" (ไม่ใช่แค่ train split) แล้วเซฟโมเดลไปใช้จริงที่ /local/classify
   — เพราะข้อมูลของเรามีน้อย (240 แถว) การเก็บ test split ไว้เฉย ๆ ไม่ใช้เทรนจะเสียของ
   — accuracy ที่รายงานยังมาจาก held-out split เท่านั้น ไม่ปนกับที่เทรนจริง
4. ถ้าเจอ tests/routing_cases.jsonl ของ member2 (40 เคสจริง) จะรันวัดผลกับชุดนั้นด้วย
   — ชุดนี้ "ห้ามเอามาเทรนเด็ดขาด" ตามที่ SCHEDULE.md กำชับ ใช้วัดผลอย่างเดียว
"""
import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "intents.csv"
MODEL_DIR = ROOT / "app" / "models"
MODEL_PATH = MODEL_DIR / "intent_clf.joblib"
MODEL_VERSION = "tfidf-logreg-v1"

# path ของ 03 ตาม 00_PLAN_OVERVIEW.md §158 — จะมีจริงเมื่อ member2 commit เข้า repo กลาง
REAL_ROUTING_CASES = ROOT.parent / "03_ai_router_agent" / "tests" / "routing_cases.jsonl"
# ชุดจำลองของเราเอง ใช้แทนชั่วคราวถ้ายังไม่มีไฟล์จริง (D4 ใช้ไฟล์นี้เดโมกระบวนการ)
SIMULATED_ROUTING_CASES = ROOT / "tests" / "simulated_routing_cases.jsonl"


def _load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    assert {"text", "intent"}.issubset(df.columns), f"{path} ต้องมีคอลัมน์ text,intent"
    return df


def _load_jsonl_cases(path: Path) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_on_routing_cases(pipeline: Pipeline, path: Path, label: str) -> None:
    if not path.exists():
        print(f"[skip] ไม่พบ {label} ที่ {path}")
        return
    cases = _load_jsonl_cases(path)
    texts = [c["query"] for c in cases]
    y_true = [c["expected_intent"] for c in cases]
    y_pred = pipeline.predict(texts)
    acc = accuracy_score(y_true, y_pred)
    print(f"\n=== ผลบน {label} ({len(cases)} เคส) — ไม่ได้เทรนด้วยชุดนี้ ===")
    print(f"accuracy: {acc:.3f}")
    misses = [
        {"query": t, "expected": e, "predicted": p}
        for t, e, p in zip(texts, y_true, y_pred)
        if e != p
    ]
    if misses:
        print(f"พลาด {len(misses)} เคส:")
        for m in misses:
            print(f"  - \"{m['query']}\" → ทาย {m['predicted']} (ที่ถูก: {m['expected']})")
    else:
        print("ไม่พลาดเลย 🎉")


def main():
    df = _load_dataset(DATA_PATH)
    X, y = df["text"].tolist(), df["intent"].tolist()

    # 1) วัด accuracy แบบ held-out (ไม่ปนกับโมเดลที่จะเอาไปใช้จริง)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    eval_pipeline = _fresh_pipeline()
    eval_pipeline.fit(X_train, y_train)
    y_pred = eval_pipeline.predict(X_test)
    held_out_acc = accuracy_score(y_test, y_pred)

    print(f"โหลดข้อมูล: {len(df)} แถว, {df['intent'].nunique()} หมวด")
    print(f"\n=== held-out accuracy (20% ของ data/intents.csv) ===")
    print(f"accuracy: {held_out_acc:.3f}")
    print(classification_report(y_test, y_pred, zero_division=0))

    # 2) เทรนโมเดลจริงด้วยข้อมูลทั้งหมด แล้วเซฟไว้ใช้ที่ /local/classify
    final_pipeline = _fresh_pipeline()
    t0 = time.monotonic()
    final_pipeline.fit(X, y)
    train_ms = int((time.monotonic() - t0) * 1000)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": final_pipeline,
            "model_version": MODEL_VERSION,
            "classes": sorted(set(y)),
            "trained_on_rows": len(df),
            "held_out_accuracy": round(held_out_acc, 4),
        },
        MODEL_PATH,
    )
    print(f"\nเทรนจบใน {train_ms}ms → เซฟโมเดลที่ {MODEL_PATH}")

    # 3) วัดกับ routing cases จริง (ถ้ามี) ไม่งั้นใช้ชุดจำลองแทน — ใช้โมเดลที่เทรนด้วย held-out split
    #    (ไม่ใช่โมเดล final ที่เทรนด้วยข้อมูลทั้งหมด กันไม่ให้ตัวเลข "รั่ว" กรณีบางเคสซ้ำกับ dataset)
    if REAL_ROUTING_CASES.exists():
        evaluate_on_routing_cases(eval_pipeline, REAL_ROUTING_CASES, "tests/routing_cases.jsonl (ของจริงจาก member2)")
    else:
        evaluate_on_routing_cases(
            eval_pipeline,
            SIMULATED_ROUTING_CASES,
            "tests/simulated_routing_cases.jsonl (ชุดจำลอง — ยังไม่ได้ไฟล์จริงจาก member2)",
        )


def _fresh_pipeline() -> Pipeline:
    # analyzer="char_wb" (char n-gram ในขอบเขตคำ) แทน word-level ธรรมดา เพราะ:
    #  - ภาษาไทยไม่มีช่องว่างคั่นคำ ถ้าตัดด้วย whitespace ประโยคไทยจะกลายเป็น "คำ" เดียวยาว ๆ
    #    (เช่น "ลิเวอร์พูลกับซิตี้ใครน่าจะชนะ" ไม่มีช่องว่างเลย) ทำให้ TF-IDF แทบไร้ประโยชน์
    #  - ไม่ต้องพึ่ง Thai word segmenter (เช่น pythainlp) เพิ่ม dependency
    #  - char n-gram (2-4 ตัวอักษร) จับ substring ของชื่อทีม/คำสำคัญได้ทั้งไทยและอังกฤษในตัวเดียว
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 4),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            ("clf", LogisticRegression(max_iter=2000, C=5.0)),
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
