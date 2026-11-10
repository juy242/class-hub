"""Đọc lại bảng nhận xét đã được giáo viên chấm và tính chỉ số (Giai đoạn 10, dòng 5 DESIGN mục 12).

Quy trình hai bước (vì cần CON NGƯỜI chấm, máy không thay được):
1. `python eval/comments_gen.py` sinh 20 nhận xét do AI viết ra `eval/comments_review.csv`
   (các cột điểm để trống).
2. 2–3 giáo viên THPT điền điểm 1–5 cho từng tiêu chí (đúng số liệu, phù hợp lứa tuổi, giọng văn)
   và đánh dấu câu tiêu cực, rồi chạy script này (hoặc make eval) để đọc lại.

CSV: mỗi dòng một nhận xét. Cột bắt đầu bằng `diem_` là điểm 1–5 (để trống nếu chưa chấm). Cột
`tieu_cuc` đánh dấu câu có từ ngữ tiêu cực (1/co/x/y). Script tính điểm trung bình trên mọi ô điểm
đã chấm và đếm số câu tiêu cực. Mục tiêu DESIGN: trung bình ≥ 4 và 0 câu tiêu cực.

Không cần DB và không cần LLM. Mã thoát 0 nếu đạt, 1 nếu chưa đạt, 2 nếu chưa có file/chưa chấm.
"""

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = EVAL_DIR / "comments_review.csv"
TARGET_MEAN = 4.0
TRUTHY = {"1", "x", "y", "yes", "co", "có", "true", "đúng"}


def _is_negative(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in TRUTHY


def evaluate(path: Path) -> tuple[int, int, int, int]:
    """Trả (tổng điểm đã chấm, số ô điểm, số câu tiêu cực, số dòng)."""
    total = count = negatives = rows = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        score_cols = [c for c in (reader.fieldnames or []) if c.lower().startswith("diem")]
        for row in reader:
            rows += 1
            if _is_negative(row.get("tieu_cuc")):
                negatives += 1
            for col in score_cols:
                raw = (row.get(col) or "").strip().replace(",", ".")
                if not raw:
                    continue
                try:
                    total += int(round(float(raw)))
                    count += 1
                except ValueError:
                    continue
    return total, count, negatives, rows


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Tính điểm nhận xét do giáo viên chấm.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(
            f"Chưa có {args.csv}. Chạy python eval/comments_gen.py để sinh, cho giáo viên chấm.",
            file=sys.stderr,
        )
        return 2

    total, count, negatives, rows = evaluate(args.csv)
    print(f"Số nhận xét: {rows}")
    if count == 0:
        print("Chưa có ô điểm nào được chấm. Nhờ giáo viên điền các cột diem_* rồi chạy lại.")
        return 2
    mean = total / count
    print(f"Điểm trung bình: {mean:.2f} (trên {count} ô điểm 1–5)")
    print(f"Số câu tiêu cực: {negatives}")
    passed = mean >= TARGET_MEAN and negatives == 0
    print(
        f"Mục tiêu DESIGN (TB ≥ {TARGET_MEAN:.0f}, 0 câu tiêu cực): "
        f"{'ĐẠT' if passed else 'CHƯA ĐẠT'}"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
