"""Nạp kết quả rèn luyện của bộ `ren-luyen-30-lop/` vào DB đang chạy, qua đúng API của hệ thống.

Chỉ dữ liệu giả lập (nguyên tắc 7). Với mỗi lớp 10A1…12A10 của năm học 2026-2027: GVCN của lớp xem
trước rồi xác nhận ba tệp (học kỳ I, học kỳ II, cả năm), đúng như thao tác ở trang "Nhập dữ liệu →
Rèn luyện" (kiểm tra từng dòng, quyền GVCN, nhật ký, cảnh báo sớm chạy lại sau khi nhập).

Cần bộ điểm 30 lớp đã nạp (`load_diem_30_lop.py`): lớp, học sinh và GVCN có sẵn. Chạy lại được:
tệp không đổi gì thì bỏ qua, không ghi trùng. Có dòng lỗi thì dừng, không ghi lớp đó.

Chạy trong container backend (cần data/samples đã chép vào /data/samples):
    PYTHONPATH=/app:/ python /data/samples/load_ren_luyen_30_lop.py
"""

import sys
from collections import Counter
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.tokens import create_access_token
from app.classes.models import ClassStudent, SchoolClass, SchoolYear, Student
from app.core.db import get_engine
from app.core.enums import UserRole
from app.main import app
from data.samples.build_diem_30_lop import CLASSES_PER_GRADE, GRADES, YEAR_CODE, YEAR_NAME
from data.samples.build_ren_luyen_30_lop import FILE_NAMES, OUTPUT

API = "/api/v1"
ADMIN_EMAIL = "admin@example.com"


def headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)[0]}"}


def check(response: Any, what: str) -> Any:
    if response.status_code >= 400:
        raise SystemExit(f"Lỗi khi {what}: {response.status_code} {response.text[:500]}")
    return response.json()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    client = TestClient(app)
    with Session(get_engine()) as session:
        year = session.scalar(select(SchoolYear).where(SchoolYear.name == YEAR_NAME))
        if year is None:
            raise SystemExit(f"Chưa có năm học {YEAR_NAME}. Chạy load_diem_30_lop.py trước.")
        classes = {
            c.name: (c.id, c.homeroom_teacher_id)
            for c in session.scalars(
                select(SchoolClass).where(SchoolClass.school_year_id == year.id)
            )
        }
        # Lớp mang danh sách của bộ 30 lớp (mã HS26…); lớp seed trùng tên (mã HS1x…) không có.
        set_class_ids = set(
            session.scalars(
                select(ClassStudent.class_id)
                .join(Student, Student.id == ClassStudent.student_id)
                .where(Student.student_code.like(f"HS{YEAR_CODE}%"))
                .distinct()
            )
        )
        admin = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if admin is None:
            raise SystemExit(f"Không có tài khoản admin {ADMIN_EMAIL}.")
        admin_id = admin.id
        homeroom_ids = {hid for _, hid in classes.values() if hid is not None}
        free_teachers = [
            (u.id, u.email)
            for u in session.scalars(
                select(User).where(User.role == UserRole.TEACHER, User.is_active.is_(True))
            )
            if u.id not in homeroom_ids
        ]
    free_teachers.sort(key=lambda t: t[1])

    # Phân giáo viên chủ nhiệm cho lớp chưa có GVCN (các lớp A4…A10 do load_diem tạo khi kế hoạch
    # GVCN @thpt-demo.local chưa có tài khoản). Dùng giáo viên seed đang rảnh (mỗi năm một GVCN một
    # lớp, D-113), qua đúng API admin (kiểm quyền, nhật ký).
    admin_headers = headers(admin_id)
    pool = iter(free_teachers)
    assigned: list[str] = []
    for grade in GRADES:
        for index in range(1, CLASSES_PER_GRADE + 1):
            name = f"{grade}A{index}"
            if name not in classes:
                raise SystemExit(f"Năm {YEAR_NAME} chưa có lớp {name}.")
            class_id, homeroom_id = classes[name]
            if homeroom_id is not None:
                continue
            teacher = next(pool, None)
            if teacher is None:
                raise SystemExit("Không đủ giáo viên đang rảnh để phân chủ nhiệm.")
            check(
                client.patch(
                    f"{API}/admin/classes/{class_id}",
                    headers=admin_headers,
                    json={"homeroom_teacher_id": teacher[0]},
                ),
                f"phân công GVCN lớp {name}",
            )
            classes[name] = (class_id, teacher[0])
            assigned.append(f"{name}: {teacher[1]}")
    if assigned:
        print(f"Đã phân chủ nhiệm {len(assigned)} lớp:", flush=True)
        for line in assigned:
            print(f"  - {line}")

    totals: Counter[str] = Counter()
    skipped: list[str] = []
    for grade in GRADES:
        for index in range(1, CLASSES_PER_GRADE + 1):
            name = f"{grade}A{index}"
            if name not in classes:
                raise SystemExit(f"Năm {YEAR_NAME} chưa có lớp {name}.")
            class_id, homeroom_id = classes[name]
            if class_id not in set_class_ids:
                print(f"{name}: giữ nguyên rèn luyện seed (khác bộ 30 lớp).", flush=True)
                continue
            if homeroom_id is None:
                skipped.append(name)
                continue
            teacher_headers = headers(homeroom_id)
            for period, file_name in FILE_NAMES.items():
                path = OUTPUT / name / f"{file_name}.xlsx"
                preview = check(
                    client.post(
                        f"{API}/classes/{class_id}/import/conduct",
                        headers=teacher_headers,
                        files={"file": (path.name, path.read_bytes(), "application/octet-stream")},
                        data={"period": period},
                    ),
                    f"xem trước {path.name} lớp {name}",
                )
                summary = preview["summary"]
                if summary["error_rows"]:
                    raise SystemExit(f"{name}/{path.name} có {summary['error_rows']} dòng lỗi.")
                if not summary["has_changes"]:
                    totals["unchanged"] += summary["total_rows"]
                    continue
                check(
                    client.post(
                        f"{API}/imports/{preview['job_id']}/confirm", headers=teacher_headers
                    ),
                    f"nhập {path.name} lớp {name}",
                )
                totals["created"] += summary["records_to_create"]
                totals["updated"] += summary["records_to_update"]
                totals["warnings"] += summary["warning_rows"]
            print(f"{name}: xong.", flush=True)

    print(
        f"Hoàn tất: {totals['created']} bản ghi mới, {totals['updated']} bản ghi cập nhật, "
        f"{totals['unchanged']} dòng giữ nguyên, {totals['warnings']} dòng cảnh báo."
    )
    if skipped:
        print("Bỏ qua (lớp chưa có GVCN): " + ", ".join(skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
