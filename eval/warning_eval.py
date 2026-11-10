"""Đánh giá mô hình cảnh báo sớm (Giai đoạn 10, dòng 4 của DESIGN mục 12).

Không huấn luyện lại ở đây (việc đó là `make train`, khoảng 2–3 phút): đọc kết quả trên tập test từ
`backend/ml/REPORT.md` do `make train` sinh ra, lấy hàng **Random Forest (chính)** và mốc **Logistic
Regression**, rồi đối chiếu mục tiêu DESIGN **Recall ≥ 0,75**.

Không cần DB và không cần LLM. Thiếu báo cáo (chưa `make train`) thì in hướng dẫn và trả mã 2.
"""

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = REPO_ROOT / "backend" / "ml" / "REPORT.md"
RECALL_TARGET = 0.75  # DESIGN mục 12

_META = re.compile(
    r"lúc\s+(?P<trained_at>\S+)\s+\(phiên bản\s+`(?P<version>[^`]+)`,\s+scikit-learn\s+"
    r"(?P<sklearn>[\d.]+)\)"
)


def _vn_float(cell: str) -> float:
    """ "0,92" -> 0.92 (số trong báo cáo dùng dấu phẩy thập phân kiểu Việt Nam)."""
    return float(cell.strip().replace(",", "."))


@dataclass
class ModelMetrics:
    name: str
    threshold: float
    recall: float
    precision: float
    f1: float


@dataclass
class WarningEvalResult:
    found: bool
    random_forest: ModelMetrics | None = None
    logistic_regression: ModelMetrics | None = None
    trained_at: str | None = None
    version: str | None = None
    sklearn: str | None = None
    note: str = ""

    @property
    def target_met(self) -> bool:
        return self.random_forest is not None and self.random_forest.recall >= RECALL_TARGET


def _parse_row(line: str) -> ModelMetrics:
    cells = [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]
    name, threshold, recall, precision, f1 = cells[:5]
    return ModelMetrics(
        name, _vn_float(threshold), _vn_float(recall), _vn_float(precision), _vn_float(f1)
    )


def evaluate(report_path: Path = DEFAULT_REPORT) -> WarningEvalResult:
    if not report_path.exists():
        return WarningEvalResult(
            found=False,
            note="Chưa có backend/ml/REPORT.md. Chạy make train để huấn luyện và sinh báo cáo.",
        )
    text = report_path.read_text(encoding="utf-8")
    result = WarningEvalResult(found=True)
    if meta := _META.search(text):
        result.trained_at = meta["trained_at"]
        result.version = meta["version"]
        result.sklearn = meta["sklearn"]
    # Chỉ lấy bảng "ngưỡng đã chọn" (hàng có chú thích "(mốc)" và "(chính)"), không phải bảng ngưỡng
    # mặc định 0,5 bên dưới.
    for line in text.splitlines():
        if line.startswith("|") and "(mốc)" in line:
            result.logistic_regression = _parse_row(line)
        elif line.startswith("|") and "(chính)" in line:
            result.random_forest = _parse_row(line)
    if result.random_forest is None:
        result.note = "REPORT.md không có hàng 'Random Forest (chính)'. Chạy lại make train."
    return result


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá mô hình cảnh báo sớm.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = evaluate(args.report)
    if not result.found or result.random_forest is None:
        print(result.note, file=sys.stderr)
        return 2

    rf, lr = result.random_forest, result.logistic_regression
    print(
        f"Mô hình: {result.version} (huấn luyện {result.trained_at}, scikit-learn {result.sklearn})"
    )
    print(f"Random Forest (chính), ngưỡng {rf.threshold:.2f}:")
    print(f"    Recall {rf.recall:.2f}  Precision {rf.precision:.2f}  F1 {rf.f1:.2f}")
    if lr is not None:
        print(f"Mốc Logistic Regression, ngưỡng {lr.threshold:.2f}:")
        print(f"    Recall {lr.recall:.2f}  Precision {lr.precision:.2f}  F1 {lr.f1:.2f}")
    print(
        f"\nMục tiêu DESIGN Recall ≥ {RECALL_TARGET:.2f}: "
        f"{'ĐẠT' if result.target_met else 'CHƯA ĐẠT'} (Recall {rf.recall:.2f})"
    )
    return 0 if result.target_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
