"""Schema request/response của API nhận xét và báo cáo (Giai đoạn 9, D-107).

Phản hồi KHÔNG bao giờ có văn bản vi phạm: bản AI viết chưa đạt kiểm tra có `text` rỗng và
`needs_manual` = true. `check_notes` chỉ là mã vi phạm (xem `checks.MESSAGES_VI`).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ReportJobStatus, ReportScope, ReportStatus, ReportType
from app.reports.permissions import STUDENT_TYPES, SUBJECT_TYPES

Semester = Literal["1", "2", "year"]
MAX_TEXT_CHARS = 5000


class ReportTarget(BaseModel):
    """Báo cáo nào, của lớp, môn, khối nào. Hình dạng hợp lệ phụ thuộc loại (D-102)."""

    type: ReportType
    semester: Semester
    class_id: int | None = None
    # int có giới hạn (không dùng Literal): tham số truy vấn đến dưới dạng chuỗi "11".
    grade_level: int | None = Field(default=None, ge=10, le=12)
    subject_id: int | None = None
    # Năm học của báo cáo khối (D-113); bỏ trống là năm hiện hành. Bản theo lớp hay học sinh luôn
    # dùng năm của lớp, giá trị này bị bỏ qua.
    school_year_id: int | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> Self:
        if self.type in SUBJECT_TYPES:
            if self.class_id is None or self.subject_id is None or self.grade_level is not None:
                raise ValueError("Bản theo môn cần class_id và subject_id, không có grade_level.")
            if self.semester == "year":
                raise ValueError("Bản theo môn chỉ viết cho học kỳ I hoặc II.")
        elif self.type in STUDENT_TYPES:
            if self.class_id is None or self.subject_id is not None or self.grade_level is not None:
                raise ValueError("Học bạ và phiếu liên lạc cần class_id, không có môn hay khối.")
        elif self.subject_id is not None or (
            self.class_id is not None and self.grade_level is not None
        ):
            # Báo cáo: lớp, hoặc khối, hoặc không gì cả (toàn trường, D-127); không bao giờ có môn.
            raise ValueError("Báo cáo chỉ nhận một trong class_id hoặc grade_level, không có môn.")
        return self


class ReportIn(ReportTarget):
    model_config = ConfigDict(extra="forbid")

    student_id: int | None = None  # có: sinh cho một em ngay; không: cả lớp, chạy nền
    feedback: str | None = Field(default=None, max_length=300)  # góp ý khi sinh lại

    @model_validator(mode="after")
    def _check_student(self) -> Self:
        if self.student_id is not None and self.type not in STUDENT_TYPES:
            raise ValueError("student_id chỉ dùng cho nhận xét học sinh.")
        if self.feedback and self.type in STUDENT_TYPES and self.student_id is None:
            raise ValueError("Góp ý chỉ dùng khi sinh cho một em hoặc một báo cáo.")
        return self


class StudentRefOut(BaseModel):
    id: int
    student_code: str
    full_name: str


class ReportOut(BaseModel):
    id: int
    type: ReportType
    type_label: str
    scope: ReportScope
    semester: Semester
    class_id: int | None
    subject_id: int | None
    target_id: int
    status: ReportStatus
    status_label: str
    text: str  # bản đã duyệt nếu có, ngược lại là bản nháp
    needs_manual: bool  # AI chưa viết được bản đạt kiểm tra: chờ giáo viên tự viết
    check_notes: list[str]  # mã vi phạm của lần sinh cuối (chỉ có ý nghĩa khi needs_manual)
    attempts: int
    model: str | None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    student: StudentRefOut | None = None
    # Cảnh báo kiểm tự động cho văn bản giáo viên sửa (không chặn việc lưu hay duyệt).
    warnings: list[str] = []


class JobOut(BaseModel):
    id: int
    class_id: int
    type: ReportType
    semester: Semester
    subject_id: int | None
    status: ReportJobStatus
    status_label: str
    total: int
    done: int
    needs_manual: int
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class ReportStudentSummaryOut(BaseModel):
    """Số liệu tóm tắt của một học sinh để giáo viên có bối cảnh khi nhận xét, đánh giá (D-124).

    Mọi số do Analytics tính (nguyên tắc 1); đây là dữ liệu giáo viên đã được xem ở nơi khác (bảng
    điểm, hồ sơ), hiện ngay cạnh ô nhận xét để khỏi phải mở trang khác.
    """

    # Phiếu liên lạc / học bạ (GVCN thấy toàn lớp):
    learning_level: str | None = None  # 'good' | 'fair' | 'pass' | 'fail' | None
    conduct_level: str | None = None
    absent_total: int | None = None
    below_pass_count: int | None = None  # số môn ĐTB dưới mức đạt
    incomplete_count: int | None = None  # số môn chưa đủ dữ liệu
    # Nhận xét môn (GVBM, chỉ môn mình dạy):
    subject_name: str | None = None
    average: float | None = None  # ĐTB môn của kỳ đang xem
    tx: list[float] | None = None  # các đầu điểm thường xuyên
    tx_missing: int | None = None
    midterm: float | None = None
    final: float | None = None
    comment_result: str | None = None  # môn nhận xét: 'pass' | 'fail'
    complete: bool | None = None


class ReportItemOut(BaseModel):
    """Một dòng của danh sách: học sinh (nhận xét) hoặc chính lớp / khối (báo cáo)."""

    student: StudentRefOut | None
    report: ReportOut | None
    summary: ReportStudentSummaryOut | None = None  # chỉ với nhận xét học sinh


class ReportListOut(BaseModel):
    items: list[ReportItemOut]
    job: JobOut | None  # lần sinh cả lớp gần nhất đang chạy (hoặc vừa dừng) cho cùng phạm vi


class ReportProgressOut(BaseModel):
    """Tiến độ một loại nhận xét của một lớp: số đã viết và số đã duyệt (D-126)."""

    written: int
    approved: int
    expected: int  # số bản cần có (sĩ số với học bạ / phiếu liên lạc); 0 = không có mẫu số cố định


class ClassReportStatusOut(BaseModel):
    """Trạng thái báo cáo tổng hợp của một lớp để BGH xem lớp nào đã có (D-126)."""

    status: ReportStatus | None = None  # None = chưa có
    status_label: str
    report_id: int | None = None


class ClassOversightOut(BaseModel):
    class_id: int
    class_name: str
    student_count: int
    school_record: ReportProgressOut  # học bạ (GVCN)
    contact_slip: ReportProgressOut  # phiếu liên lạc (GVCN)
    subject_comment: ReportProgressOut  # nhận xét môn (GVBM, nhiều môn nên không có mẫu số cố định)
    class_report: ClassReportStatusOut  # báo cáo tổng hợp của lớp


class GradeOversightOut(BaseModel):
    """Bảng giám sát tiến độ nhận xét của cả một khối, chỉ BGH xem (D-126). Chỉ số đếm."""

    grade_level: int
    semester: Semester
    classes: list[ClassOversightOut]


class ReportUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    approve: bool = False

    @model_validator(mode="after")
    def _needs_something(self) -> Self:
        if self.text is None and not self.approve:
            raise ValueError("Cần text hoặc approve.")
        return self


class RegenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str | None = Field(default=None, max_length=300)
