"""Đánh giá bộ tính điểm Thông tư 22 (Giai đoạn 10, dòng 1 của DESIGN mục 12).

Chạy: `make eval` (gộp chung) hoặc `python eval/analytics_eval.py [--only S01,L10]`.

Chạy 30 ca trong `eval/analytics_cases.json` QUA chính mã `app/analytics/` (ĐTBmhk, ĐTBmcn, mức
học tập, điều kiện lên lớp) và so với kết quả đã tính tay lưu trong JSON. Chỉ số: **% khớp**, mục
tiêu DESIGN 100%.

KHÔNG cần DB và KHÔNG cần LLM: các hàm công thức là hàm thuần, cấu hình (hệ số, ngưỡng) đặt cố định
trong file này đúng như phần "about" của bộ ca, nên một lần chạy luôn cho cùng kết quả và không phụ
thuộc trạng thái bảng `settings`. Mã thoát 0 nếu khớp 100%, 1 nếu có ca lệch.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.analytics.conduct import PeriodConduct  # noqa: E402
from app.analytics.config import AnalyticsConfig  # noqa: E402
from app.analytics.learning import LearningResult, SubjectResult, learning_result  # noqa: E402
from app.analytics.promotion import promotion_status  # noqa: E402
from app.analytics.scores import semester_average_from_scores, year_average  # noqa: E402
from app.core.enums import AssessmentType, CommentResult, ConductLevel  # noqa: E402

DEFAULT_CASES = REPO_ROOT / "eval" / "analytics_cases.json"
TARGET = 1.0  # DESIGN mục 12: 100%

# Cấu hình đúng như phần "about" của bộ ca: hệ số giữa kỳ 2, cuối kỳ 3, HK2 trong cả năm 2; ngưỡng
# 3,5 / 5,0 / 6,5 / 8,0; tối thiểu 6 môn; nghỉ tối đa 45; bật điều chỉnh mức. Các khoá không liên
# quan tới bốn nhóm công thức (số đầu điểm thường xuyên, ngưỡng cảnh báo nghỉ) đặt giá trị hợp lệ.
CONFIG = AnalyticsConfig(
    coef_midterm=Decimal(2),
    coef_final=Decimal(3),
    coef_year_semester2=Decimal(2),
    score_threshold_fail=Decimal("3.5"),
    score_threshold_pass=Decimal("5.0"),
    score_threshold_fair=Decimal("6.5"),
    score_threshold_good=Decimal("8.0"),
    level_min_subjects=6,
    max_absent_sessions=45,
    absent_warning_notice=30,
    absent_warning_high=40,
    regular_assessment_count=(),
    level_single_subject_adjustment=True,
)

COMMENT = {"pass": CommentResult.PASS, "fail": CommentResult.FAIL}


@dataclass
class CaseResult:
    case_id: str
    title: str
    ok: bool
    detail: str = ""  # mô tả lệch khi ok=False (mong đợi vs nhận được)


@dataclass
class EvalResult:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.ok)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def _subjects(scores: Sequence[str], comments: Sequence[str]) -> list[SubjectResult]:
    """Dựng danh sách môn: môn điểm số đánh số id từ 1, môn nhận xét từ 101 (quy ước của bộ ca)."""
    results = [
        SubjectResult(
            subject_id=i + 1,
            name=f"Môn {i + 1}",
            assessment_type=AssessmentType.SCORE,
            average=Decimal(value),
            complete=True,
        )
        for i, value in enumerate(scores)
    ]
    results += [
        SubjectResult(
            subject_id=101 + j,
            name=f"Môn NX {j + 1}",
            assessment_type=AssessmentType.COMMENT,
            comment_result=COMMENT[value],
            complete=True,
        )
        for j, value in enumerate(comments)
    ]
    return results


def _check(case_id: str, title: str, checks: list[tuple[str, Any, Any]]) -> CaseResult:
    """Mỗi mục là (nhãn, mong đợi, nhận được); ca đạt khi mọi mục bằng nhau."""
    diffs = [
        f"{label}: mong {exp!r} nhưng được {got!r}" for label, exp, got in checks if exp != got
    ]
    return CaseResult(case_id, title, not diffs, "; ".join(diffs))


def _semester_case(case: dict[str, Any]) -> CaseResult:
    got = semester_average_from_scores(
        [Decimal(x) for x in case["tx"]],
        None if case.get("midterm") is None else Decimal(case["midterm"]),
        None if case.get("final") is None else Decimal(case["final"]),
        CONFIG,
    )
    exp = None if case["expected"] is None else Decimal(case["expected"])
    return _check(case["id"], case["title"], [("ĐTBmhk", exp, got)])


def _year_case(case: dict[str, Any]) -> CaseResult:
    got = year_average(Decimal(case["semester1"]), Decimal(case["semester2"]), CONFIG)
    exp = None if case["expected"] is None else Decimal(case["expected"])
    return _check(case["id"], case["title"], [("ĐTBmcn", exp, got)])


def _level_value(level: ConductLevel | None) -> str | None:
    return None if level is None else level.value


def _learning_case(case: dict[str, Any]) -> CaseResult:
    result: LearningResult = learning_result(_subjects(case["scores"], case["comments"]), CONFIG)
    return _check(
        case["id"],
        case["title"],
        [
            ("mức", case["expected_level"], _level_value(result.level)),
            ("mức gốc", case["expected_base_level"], _level_value(result.base_level)),
            ("điều chỉnh", case["expected_adjusted"], result.adjusted),
        ],
    )


def _promotion_case(case: dict[str, Any]) -> CaseResult:
    year_subjects = _subjects(case["scores"], case["comments"])
    learning = learning_result(year_subjects, CONFIG)
    conduct_value = case["conduct"]
    conduct = PeriodConduct(
        None if conduct_value is None else ConductLevel(conduct_value),
        derived=case["conduct_derived"],
    )
    result = promotion_status(
        learning=learning,
        year_subjects=year_subjects,
        conduct=conduct,
        absent_sessions=case["absent"],
        config=CONFIG,
    )
    got_retake = sorted((s.subject_id, s.reason.value) for s in result.retake_subjects)
    exp_retake = sorted((r["subject_id"], r["reason"]) for r in case["expected_retake"])
    return _check(
        case["id"],
        case["title"],
        [
            ("đủ điều kiện", case["expected_eligible"], result.eligible),
            ("lý do", case["expected_reasons"], [r.value for r in result.reasons]),
            ("kiểm tra lại", exp_retake, got_retake),
        ],
    )


RUNNERS = {
    "semester_average": _semester_case,
    "year_average": _year_case,
    "learning_level": _learning_case,
    "promotion": _promotion_case,
}


def evaluate(cases_path: Path = DEFAULT_CASES, only: set[str] | None = None) -> EvalResult:
    data = json.loads(cases_path.read_text(encoding="utf-8"))
    result = EvalResult()
    for group, runner in RUNNERS.items():
        for case in data.get(group, []):
            if only and case["id"] not in only:
                continue
            result.cases.append(runner(case))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Đánh giá bộ tính điểm Thông tư 22.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--only", default="", help="chỉ chạy các mã ca, ví dụ S01,L10")
    args = parser.parse_args(argv)
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    result = evaluate(args.cases, only or None)
    for case in result.cases:
        mark = "ĐÚNG " if case.ok else "LỆCH "
        line = f"{mark}{case.case_id}: {case.title}"
        print(line if case.ok else f"{line}\n        {case.detail}")

    print(
        f"\nTính điểm Thông tư 22 — % khớp: {result.passed}/{result.total} = "
        f"{100 * result.rate:.0f}%"
    )
    print(f"Mục tiêu DESIGN {TARGET:.0%}: {'ĐẠT' if result.rate >= TARGET else 'CHƯA ĐẠT'}")
    return 0 if result.rate >= TARGET else 1


if __name__ == "__main__":
    raise SystemExit(main())
