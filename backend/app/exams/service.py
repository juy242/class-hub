"""Đăng ký thi tốt nghiệp của lớp 12: GVCN nhập/sửa môn tự chọn, GVCN tự khóa (D-128).

Quyền (nguyên tắc 4, gọi TRƯỚC khi đọc dữ liệu):
- Xem: authorize() + require_all_subjects() → GVCN của lớp và BGH; GVBM (chỉ vài môn) và Admin bị từ
  chối (môn thi là dữ liệu học tập của từng em, admin không xem — D-077/D-087).
- Sửa / khóa / mở: authorize_write() không môn → chỉ GVCN của lớp.

Chỉ khối 12 có đăng ký thi. Toán + Ngữ văn luôn bắt buộc; mỗi em chọn đúng 2 môn tự chọn trong các
môn tính điểm của lớp. Đã khóa thì chặn mọi sửa cho tới khi GVCN tự mở.
"""

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.analytics import repository as analytics_repo
from app.analytics.repository import SubjectInfo
from app.analytics.schemas import ClassRefOut
from app.auth.audit import record_access
from app.auth.models import User
from app.classes.academic import ExamRegistration, ExamRegistrationLock
from app.core.authorize import AuthorizationError, authorize, authorize_write
from app.core.enums import AuditAction
from app.exams.rules import COMPULSORY_SUBJECTS, ELECTIVE_COUNT, is_compulsory, is_eligible_elective
from app.exams.schemas import (
    ClassExamRegistrationsOut,
    ElectivesIn,
    StudentRegistrationOut,
    SubjectRefOut,
)

GRADE_12 = 12


class NotFound(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Invalid(Exception):
    """Yêu cầu đúng hình dạng nhưng không hợp dữ liệu (môn không hợp lệ, không đủ số môn…)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Locked(Exception):
    """Đăng ký của lớp đã được chốt; phải mở khóa trước khi sửa."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class _Lock:
    locked: bool
    locked_at: object | None
    locked_by: str | None


def _can(fn: object) -> bool:
    try:
        fn()  # type: ignore[operator]
    except AuthorizationError:
        return False
    return True


def _class_ref(session: Session, class_id: int) -> ClassRefOut:
    info = analytics_repo.get_class(session, class_id)
    if info is None:
        raise NotFound("Không có lớp này.")
    if info.grade_level != GRADE_12:
        raise NotFound("Chỉ khối 12 có đăng ký thi tốt nghiệp.")
    return ClassRefOut(id=info.id, name=info.name, grade_level=info.grade_level)


def _subjects(session: Session, class_id: int) -> list[SubjectInfo]:
    return analytics_repo.class_subjects(session, class_id)


def _compulsory(subjects: list[SubjectInfo]) -> list[SubjectInfo]:
    # Giữ thứ tự Toán, Ngữ văn như hiển thị mong muốn thì sắp theo COMPULSORY_SUBJECTS.
    found = [s for s in subjects if is_compulsory(s.name)]
    order = {name: i for i, name in enumerate(COMPULSORY_SUBJECTS)}
    return sorted(found, key=lambda s: order.get(s.name, len(order)))


def _electives(subjects: list[SubjectInfo]) -> list[SubjectInfo]:
    return [s for s in subjects if is_eligible_elective(s)]


def _lock_info(session: Session, class_id: int) -> _Lock:
    row = session.execute(
        select(ExamRegistrationLock.locked_at, User.full_name)
        .join(User, User.id == ExamRegistrationLock.locked_by)
        .where(ExamRegistrationLock.class_id == class_id)
    ).one_or_none()
    if row is None:
        return _Lock(False, None, None)
    return _Lock(True, row[0], row[1])


def get_registrations(session: Session, user: User, class_id: int) -> ClassExamRegistrationsOut:
    authorize(session, user, class_id=class_id).require_all_subjects()
    class_ref = _class_ref(session, class_id)
    subjects = _subjects(session, class_id)
    compulsory = _compulsory(subjects)
    electives = _electives(subjects)
    elective_ids = {s.id for s in electives}
    students = analytics_repo.class_students(session, class_id)
    registered = analytics_repo.exam_subjects(session, class_id)
    lock = _lock_info(session, class_id)
    can_manage = _can(lambda: authorize_write(session, user, class_id=class_id))

    rows: list[StudentRegistrationOut] = []
    for student in students:
        chosen = [
            sid for sid in registered.get(student.class_student_id, []) if sid in elective_ids
        ]
        rows.append(
            StudentRegistrationOut(
                student_id=student.student_id,
                student_code=student.student_code,
                full_name=student.full_name,
                elective_subject_ids=chosen,
                complete=len(chosen) == ELECTIVE_COUNT,
            )
        )

    out = ClassExamRegistrationsOut(
        class_info=class_ref,
        can_manage=can_manage,
        can_edit=can_manage and not lock.locked,
        locked=lock.locked,
        locked_at=lock.locked_at,  # type: ignore[arg-type]
        locked_by=lock.locked_by,
        elective_count=ELECTIVE_COUNT,
        compulsory=[SubjectRefOut(id=s.id, name=s.name) for s in compulsory],
        elective_options=[SubjectRefOut(id=s.id, name=s.name) for s in electives],
        students=rows,
    )
    record_access(
        session,
        user,
        AuditAction.VIEW_EXAM_REGISTRATION,
        class_id=class_id,
        details={"student_count": len(students)},
    )
    return out


def set_electives(
    session: Session, user: User, class_id: int, student_id: int, data: ElectivesIn
) -> ClassExamRegistrationsOut:
    """Đặt lại 2 môn tự chọn của một em. Môn bắt buộc tự giữ/thêm. Trả về cả lớp sau khi sửa."""
    authorize_write(session, user, class_id=class_id)  # chỉ GVCN của lớp
    _class_ref(session, class_id)
    if _lock_info(session, class_id).locked:
        raise Locked("Đăng ký của lớp đã được chốt. Hãy mở khóa trước khi sửa.")

    subjects = _subjects(session, class_id)
    student = next(
        (s for s in analytics_repo.class_students(session, class_id) if s.student_id == student_id),
        None,
    )
    if student is None:
        raise Invalid("Học sinh không thuộc lớp này.")

    if not data.count_ok:
        raise Invalid(f"Phải chọn đúng {ELECTIVE_COUNT} môn tự chọn khác nhau.")
    elective_ids = {s.id for s in _electives(subjects)}
    chosen = data.distinct_ids()
    if any(sid not in elective_ids for sid in chosen):
        raise Invalid(
            "Có môn không hợp lệ: chỉ chọn môn tính điểm lớp đang học, không phải môn thi."
        )

    compulsory_ids = {s.id for s in _compulsory(subjects)}
    desired = compulsory_ids | set(chosen)
    existing = {
        r.subject_id: r
        for r in session.scalars(
            select(ExamRegistration).where(
                ExamRegistration.class_student_id == student.class_student_id
            )
        )
    }
    for subject_id, row in existing.items():
        if subject_id not in desired:
            session.delete(row)
    for subject_id in desired:
        if subject_id not in existing:
            session.add(
                ExamRegistration(class_student_id=student.class_student_id, subject_id=subject_id)
            )
    record_access(
        session,
        user,
        AuditAction.EDIT_EXAM_REGISTRATION,
        class_id=class_id,
        details={"student_id": student_id, "electives": chosen},
        commit=False,
    )
    session.commit()
    return get_registrations(session, user, class_id)


def lock(session: Session, user: User, class_id: int) -> ClassExamRegistrationsOut:
    """GVCN chốt (khóa) đăng ký của lớp."""
    authorize_write(session, user, class_id=class_id)
    _class_ref(session, class_id)
    if _lock_info(session, class_id).locked:
        raise Invalid("Đăng ký của lớp đã được chốt rồi.")
    session.add(ExamRegistrationLock(class_id=class_id, locked_by=user.id))
    record_access(
        session,
        user,
        AuditAction.LOCK_EXAM_REGISTRATION,
        class_id=class_id,
        details={},
        commit=False,
    )
    session.commit()
    return get_registrations(session, user, class_id)


def unlock(session: Session, user: User, class_id: int) -> ClassExamRegistrationsOut:
    """GVCN mở khóa để sửa lại (ví dụ học sinh đổi môn tự chọn)."""
    authorize_write(session, user, class_id=class_id)
    _class_ref(session, class_id)
    if not _lock_info(session, class_id).locked:
        raise Invalid("Đăng ký của lớp chưa khóa.")
    session.execute(delete(ExamRegistrationLock).where(ExamRegistrationLock.class_id == class_id))
    record_access(
        session,
        user,
        AuditAction.UNLOCK_EXAM_REGISTRATION,
        class_id=class_id,
        details={},
        commit=False,
    )
    session.commit()
    return get_registrations(session, user, class_id)
