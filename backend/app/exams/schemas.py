"""Schema quản lý đăng ký thi tốt nghiệp của lớp 12 (D-128)."""

from datetime import datetime

from pydantic import BaseModel

from app.analytics.schemas import ClassRefOut
from app.exams.rules import ELECTIVE_COUNT


class SubjectRefOut(BaseModel):
    id: int
    name: str


class StudentRegistrationOut(BaseModel):
    student_id: int
    student_code: str
    full_name: str
    # id các môn tự chọn em đang đăng ký (môn bắt buộc không liệt kê ở đây, luôn có).
    elective_subject_ids: list[int]
    complete: bool  # đã chọn đủ số môn tự chọn


class ClassExamRegistrationsOut(BaseModel):
    class_info: ClassRefOut
    can_manage: bool  # GVCN của lớp: được khóa / mở (kể cả khi đang khóa)
    can_edit: bool  # GVCN của lớp và lớp chưa khóa: được sửa môn tự chọn
    locked: bool
    locked_at: datetime | None
    locked_by: str | None  # tên người đã khóa
    elective_count: int  # số môn tự chọn cần có (2)
    compulsory: list[SubjectRefOut]  # môn bắt buộc (Toán, Ngữ văn)
    elective_options: list[SubjectRefOut]  # các môn được phép chọn làm môn tự chọn
    students: list[StudentRegistrationOut]


class ElectivesIn(BaseModel):
    # Đúng ELECTIVE_COUNT môn tự chọn; kiểm tra "hợp lệ" (môn của lớp, đủ điều kiện thi) ở service
    # vì cần tra dữ liệu lớp.
    elective_subject_ids: list[int]

    def distinct_ids(self) -> list[int]:
        return list(dict.fromkeys(self.elective_subject_ids))

    @property
    def count_ok(self) -> bool:
        ids = self.distinct_ids()
        return len(ids) == len(self.elective_subject_ids) == ELECTIVE_COUNT
