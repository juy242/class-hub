"""Sinh nhận xét do AI viết ra CSV để giáo viên chấm (Giai đoạn 10, dòng 5 DESIGN mục 12, bước 1).

Chạy: `python eval/comments_gen.py [--class 11A2] [--semester 1] [--count 5] [--type contact_slip]`.

Sinh `--count` phiếu liên lạc (hoặc học bạ) cho các học sinh đầu lớp, đi qua ĐÚNG pipeline sản phẩm
(`reports.service.generate`): phân quyền của GVCN, lấy số liệu từ Analytics, ẩn danh, gọi LLM, bộ
kiểm tự động. Ghi mỗi nhận xét một dòng vào `eval/comments_review.csv` với các cột điểm để TRỐNG,
rồi XOÁ các bản nháp vừa tạo (không để lẫn vào dữ liệu thật). Sau đó 2–3 giáo viên điền điểm 1–5 và
đánh dấu câu tiêu cực; `comments_eval.py` đọc lại.

Cần DB đã seed và LLM đã cấu hình. Mỗi nhận xét tốn vài lượt gọi; gói Gemini miễn phí 20 lượt/ngày
nên để `--count` nhỏ (hoặc đổi `LLM_MODEL`). DESIGN đề xuất 20 nhận xét: `--count 20` khi trả phí.
"""

import argparse
import csv
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import delete, text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.analytics import repository as repo  # noqa: E402
from app.assistant.llm import LLMError, LLMNotConfigured  # noqa: E402
from app.assistant.providers import get_llm_provider  # noqa: E402
from app.auth.models import User  # noqa: E402
from app.core.db import get_session_factory  # noqa: E402
from app.core.enums import ReportType  # noqa: E402
from app.reports import service as reports_service  # noqa: E402
from app.reports.models import Report  # noqa: E402
from app.reports.schemas import ReportIn  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
DEFAULT_OUT = EVAL_DIR / "comments_review.csv"
TYPES = {"contact_slip": ReportType.CONTACT_SLIP, "school_record": ReportType.SCHOOL_RECORD}
COLUMNS = [
    "id",
    "loai",
    "lop",
    "hoc_sinh",
    "noi_dung",
    "diem_so_lieu",  # 1–5: nhận xét có bám đúng số liệu không
    "diem_lua_tuoi",  # 1–5: phù hợp lứa tuổi THPT
    "diem_giong_van",  # 1–5: giọng văn tự nhiên, khích lệ
    "tieu_cuc",  # đánh dấu (x) nếu có từ ngữ tiêu cực / so sánh / nhắc hoàn cảnh
    "ghi_chu",
]


def _resolve_class(session, name: str) -> tuple[int, int | None]:
    row = session.execute(
        text(
            "SELECT c.id, c.homeroom_teacher_id FROM classes c "
            "JOIN school_years y ON y.id = c.school_year_id AND y.is_current "
            "WHERE c.name = :n"
        ),
        {"n": name},
    ).first()
    if row is None:
        raise SystemExit(f"Không có lớp {name} ở năm học hiện hành. Chạy make seed.")
    return int(row[0]), (int(row[1]) if row[1] is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description="Sinh nhận xét AI ra CSV để giáo viên chấm.")
    parser.add_argument("--class", dest="class_name", default="11A2")
    parser.add_argument("--semester", default="1", choices=["1", "2"])
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--type", default="contact_slip", choices=list(TYPES))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    report_type = TYPES[args.type]

    try:
        provider = get_llm_provider()
    except LLMNotConfigured as error:
        print(
            f"Chưa cấu hình LLM: {error}. Đặt LLM_PROVIDER và LLM_API_KEY trong .env.",
            file=sys.stderr,
        )
        return 2

    rows: list[dict[str, str]] = []
    created: list[int] = []
    try:
        with get_session_factory()() as session:
            class_id, homeroom_id = _resolve_class(session, args.class_name)
            if homeroom_id is None:
                print(f"Lớp {args.class_name} chưa có giáo viên chủ nhiệm.", file=sys.stderr)
                return 2
            gvcn = session.get(User, homeroom_id)
            if gvcn is None:
                print("Không tìm thấy tài khoản giáo viên chủ nhiệm.", file=sys.stderr)
                return 2
            students = repo.class_students(session, class_id)[: args.count]
            print(
                f"Sinh {len(students)} nhận xét ({args.type}) lớp {args.class_name} "
                f"bằng {provider.model}..."
            )
            for i, student in enumerate(students, start=1):
                body = ReportIn(
                    type=report_type,
                    semester=args.semester,
                    class_id=class_id,
                    student_id=student.student_id,
                )
                try:
                    out = reports_service.generate(session, gvcn, get_llm_provider, body)
                except reports_service.Conflict:
                    print(f"  C{i:02d}: đã có bản (bỏ qua).")
                    continue
                except (LLMError, reports_service.GenerationBlocked) as error:
                    print(f"  C{i:02d}: LỖI {type(error).__name__}: {error}", file=sys.stderr)
                    return 2
                created.append(out.id)
                note = "AI chưa viết được bản đạt kiểm tra" if out.needs_manual else ""
                rows.append(
                    {
                        "id": f"C{i:02d}",
                        "loai": args.type,
                        "lop": args.class_name,
                        "hoc_sinh": f"Học sinh {i}",
                        "noi_dung": " ".join((out.text or "").split()),
                        "diem_so_lieu": "",
                        "diem_lua_tuoi": "",
                        "diem_giong_van": "",
                        "tieu_cuc": "",
                        "ghi_chu": note,
                    }
                )
                print(f"  C{i:02d}: {'cần tự viết' if out.needs_manual else 'xong'}")
            if created:  # dọn bản nháp vừa tạo, không để lẫn dữ liệu thật
                session.execute(delete(Report).where(Report.id.in_(created)))
                session.commit()
    except OperationalError:
        print(
            "Không kết nối được PostgreSQL. Chạy make db, make migrate, make seed.", file=sys.stderr
        )
        return 2

    if not rows:
        print("Không sinh được nhận xét nào.", file=sys.stderr)
        return 2
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"\nĐã ghi {len(rows)} nhận xét vào {args.out}.\n"
        "Nhờ 2–3 giáo viên điền các cột diem_* (1–5) và đánh dấu tieu_cuc, rồi chạy "
        "python eval/comments_eval.py (hoặc make eval)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
