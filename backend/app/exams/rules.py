"""Quy tắc môn thi tốt nghiệp THPT (D-128). Khớp dữ liệu seed (data/seed/generate.py).

Từ 2025 kỳ thi tốt nghiệp có 2 môn bắt buộc (Toán, Ngữ văn) và 2 môn tự chọn. Môn tự chọn phải là
môn tính điểm mà lớp đang học, không phải môn bắt buộc và không thuộc nhóm không thi.
"""

from app.analytics.repository import SubjectInfo
from app.core.enums import AssessmentType

COMPULSORY_SUBJECTS: tuple[str, ...] = ("Ngữ văn", "Toán")
EXCLUDED_SUBJECTS: tuple[str, ...] = ("Giáo dục quốc phòng và an ninh",)
ELECTIVE_COUNT = 2


def is_compulsory(name: str) -> bool:
    return name in COMPULSORY_SUBJECTS


def is_eligible_elective(subject: SubjectInfo) -> bool:
    """Môn được phép chọn làm môn thi tự chọn của lớp."""
    return (
        subject.assessment_type is AssessmentType.SCORE
        and subject.name not in COMPULSORY_SUBJECTS
        and subject.name not in EXCLUDED_SUBJECTS
    )
