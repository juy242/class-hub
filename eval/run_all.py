"""Bộ điều phối đánh giá AI (Giai đoạn 10, DESIGN mục 12): chạy mọi bộ và ghi eval/REPORT.md.

Chạy: `make eval` (hoặc `python eval/run_all.py [--skip-llm]`).

Gọi lần lượt từng script con bằng subprocess, trích chỉ số từ đầu ra, rồi ghi bảng 6 dòng của
DESIGN mục 12 vào `eval/REPORT.md` kèm ngày chạy, model LLM và phiên bản lời nhắc.

- Dòng 1 (Analytics) và 4 (Cảnh báo) không cần LLM, luôn chạy.
- Dòng 3 (RAG, Hit@4 và từ chối) cần DB và mô hình embedding, luôn chạy nếu có.
- Dòng 2 (Trợ lý) và 6 (Bảo mật) cần LLM; `--skip-llm` hoặc chưa cấu hình LLM thì bỏ qua, ghi
  "chưa chạy".
- Dòng 5 (Nhận xét) cần giáo viên chấm: đọc eval/comments_review.csv nếu có (xem comments_eval.py),
  chưa có thì ghi "chờ giáo viên chấm".

Mã thoát 0 nếu mọi dòng ĐÃ CHẠY đều đạt mục tiêu; 1 nếu có dòng chưa đạt.
"""

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
REPORT = EVAL_DIR / "REPORT.md"
COMMENTS_REVIEW = EVAL_DIR / "comments_review.csv"

# Chế độ --sample: mẫu đại diện nhỏ vừa hạn mức Gemini miễn phí (20 lượt/ngày/mô hình). Mỗi câu tốn
# vài lượt gọi (các vòng gọi hàm), nên chỉ chọn vài câu phủ các hàm và nhóm tấn công tiêu biểu.
SAMPLE_ASSISTANT = "A09,A13,A24,A32"  # điểm môn, tổng quan khối, chuyên cần, tra quy định
SAMPLE_SECURITY = "SEC04,SEC12,SEC14"  # hỏi môn khác, leo thang quyền, hỏi phụ huynh


@dataclass
class Row:
    component: str
    metric: str = "—"
    target: str = "—"
    status: str = "chưa chạy"  # ĐẠT | CHƯA ĐẠT | chưa chạy | chờ giáo viên chấm
    notes: str = ""


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    model: str = "—"
    notes: list[str] = field(default_factory=list)

    def ran_and_failed(self) -> bool:
        return any(r.status == "CHƯA ĐẠT" for r in self.rows)


def _run(script: str, extra: Sequence[str] = ()) -> tuple[int, str]:
    """Chạy một script con; trả (mã thoát, đầu ra gộp stdout+stderr)."""
    proc = subprocess.run(
        [sys.executable, str(EVAL_DIR / script), *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONPATH": os.environ.get("PYTHONPATH", str(REPO_ROOT / "backend"))},
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _search(pattern: str, text: str, default: str = "—") -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else default


def _analytics(report: Report) -> None:
    code, out = _run("analytics_eval.py")
    metric = _search(r"% khớp:\s*(\d+/\d+ = \d+%)", out)
    report.rows.append(
        Row("1. Tính điểm Thông tư 22", metric, "100%", "ĐẠT" if code == 0 else "CHƯA ĐẠT")
    )


def _warning(report: Report) -> None:
    code, out = _run("warning_eval.py")
    if code == 2:
        report.rows.append(
            Row("4. Mô hình cảnh báo", target="Recall ≥ 0,75", notes="chưa make train")
        )
        return
    recall = _search(r"Recall ([\d.]+)\)", out)
    report.rows.append(
        Row(
            "4. Mô hình cảnh báo",
            f"Recall {recall}" if recall != "—" else "—",
            "Recall ≥ 0,75",
            "ĐẠT" if code == 0 else "CHƯA ĐẠT",
        )
    )


def _rag(report: Report) -> None:
    code, out = _run("rag_eval.py")
    if code == 2:
        report.rows.append(
            Row("3. RAG văn bản quy định", target="≥ 80%", notes="chưa nạp văn bản / mô hình")
        )
        return
    hit = _search(r"Hit@4 \(tìm đúng điều\):\s*(\d+/\d+ = \d+%)", out)
    refuse = _search(r"Từ chối đúng câu ngoài phạm vi:\s*(\d+/\d+ = \d+%)", out)
    report.rows.append(
        Row(
            "3. RAG văn bản quy định",
            f"Hit@4 {hit}; từ chối {refuse}",
            "≥ 80%",
            "ĐẠT" if code == 0 else "CHƯA ĐẠT",
            "“% trả lời đúng” cần LLM (đo qua bộ Trợ lý, các câu quy định)",
        )
    )


def _assistant(report: Report, skip: bool, sample: bool) -> None:
    row = Row("2. Trợ lý hỏi dữ liệu", target="≥ 85%")
    if skip:
        row.notes = "bỏ qua (--skip-llm)"
        report.rows.append(row)
        return
    extra = ["--only", SAMPLE_ASSISTANT] if sample else []
    code, out = _run("assistant_eval.py", extra)
    if code == 2:
        row.notes = "chưa cấu hình LLM"
        report.rows.append(row)
        return
    tool = _search(r"Chọn đúng hàm:\s*(\d+/\d+ = \d+%)", out)
    number = _search(r"Đúng số liệu:\s*(\d+/\d+ = \d+%)", out)
    refuse = _search(r"Từ chối đúng:\s*(\d+/\d+ = \d+%)", out)
    report.model = _search(r"Mô hình:\s*(.+)", out, report.model)
    row.metric = f"đúng hàm {tool}; đúng số {number}; từ chối {refuse}"
    row.status = "ĐẠT" if code == 0 else "CHƯA ĐẠT"
    if sample:
        row.notes = f"mẫu nhỏ {SAMPLE_ASSISTANT} (hạn mức free); bộ 50 câu chạy khi có khóa trả phí"
    report.rows.append(row)


def _security(report: Report, skip: bool, sample: bool) -> None:
    row = Row("6. Phân quyền & bảo mật AI", target="100%")
    if skip:
        row.notes = "bỏ qua (--skip-llm)"
        report.rows.append(row)
        return
    extra = ["--only", SAMPLE_SECURITY] if sample else []
    code, out = _run("security_eval.py", extra)
    if code == 2:
        row.notes = "chưa cấu hình LLM (hoặc có câu lỗi gọi LLM)"
        report.rows.append(row)
        return
    row.metric = _search(r"An toàn:\s*(\d+/\d+ = \d+%)", out)
    report.model = _search(r"Mô hình:\s*(.+)", out, report.model)
    row.status = "ĐẠT" if code == 0 else "CHƯA ĐẠT"
    if sample:
        row.notes = f"mẫu nhỏ {SAMPLE_SECURITY} (hạn mức free); bộ 20 câu chạy khi có khóa trả phí"
    report.rows.append(row)


def _comments(report: Report) -> None:
    row = Row("5. Nhận xét do AI viết", target="TB ≥ 4; 0 câu tiêu cực")
    if not COMMENTS_REVIEW.exists():
        row.status = "chờ giáo viên chấm"
        row.notes = "chạy comments_gen.py để sinh CSV, cho giáo viên chấm, rồi comments_eval.py"
        report.rows.append(row)
        return
    code, out = _run("comments_eval.py")
    row.metric = _search(r"Điểm trung bình:\s*(.+)", out)
    neg = _search(r"Số câu tiêu cực:\s*(\d+)", out)
    row.notes = f"{neg} câu tiêu cực" if neg != "—" else ""
    row.status = "ĐẠT" if code == 0 else "CHƯA ĐẠT"
    report.rows.append(row)


def build_report(skip_llm: bool, sample: bool) -> Report:
    report = Report()
    _analytics(report)
    _assistant(report, skip_llm, sample)
    _rag(report)
    _warning(report)
    _comments(report)
    _security(report, skip_llm, sample)
    return report


def write_report(report: Report) -> None:
    now = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M %z")
    lines = [
        "# Báo cáo đánh giá AI",
        "",
        "Sinh tự động bởi `make eval` (`eval/run_all.py`). **Đừng sửa tay.**",
        "",
        f"- Thời điểm chạy: {now}",
        f"- Model LLM: {report.model}",
        "- Phiên bản lời nhắc: Trợ lý `system_v1.vi`, Nhận xét `reports-v1`",
        "",
        "## Kết quả theo DESIGN mục 12",
        "",
        "| Thành phần | Chỉ số | Kết quả | Mục tiêu | Đạt? |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in report.rows:
        note = f" <br><sub>{r.notes}</sub>" if r.notes else ""
        lines.append(f"| {r.component} | {r.metric}{note} | — | {r.target} | {r.status} |")
    lines += [
        "",
        "Ghi chú:",
        "- Số đo tính trên dữ liệu giả lập (`data/seed/`), đã scope theo năm học hiện hành.",
        "- Mẫu còn nhỏ: con số để theo dõi xu hướng, chưa đủ kết luận thống kê.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Chạy toàn bộ đánh giá AI và ghi REPORT.md.")
    parser.add_argument("--skip-llm", action="store_true", help="bỏ qua các bộ cần LLM")
    parser.add_argument(
        "--sample", action="store_true", help="chỉ chạy mẫu nhỏ các bộ LLM (vừa hạn mức free)"
    )
    args = parser.parse_args(argv)

    report = build_report(args.skip_llm, args.sample)
    write_report(report)
    print(f"Đã ghi {REPORT}")
    for r in report.rows:
        print(f"  {r.component}: {r.metric} -> {r.status}")
    return 1 if report.ran_and_failed() else 0


if __name__ == "__main__":
    raise SystemExit(main())
