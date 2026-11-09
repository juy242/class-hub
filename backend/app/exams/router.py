"""API quản lý đăng ký thi tốt nghiệp của lớp 12 (D-128).

Mọi hàm của service gọi authorize() / authorize_write() TRƯỚC khi đọc dữ liệu (nguyên tắc 4); lỗi
quyền → 403 do handler chung.
"""

from fastapi import APIRouter, HTTPException, status

from app.auth.deps import CurrentUser
from app.core.db import DbSession
from app.exams import service
from app.exams.schemas import ClassExamRegistrationsOut, ElectivesIn

router = APIRouter(tags=["exam-registrations"])


def _http(error: Exception) -> HTTPException:
    if isinstance(error, service.NotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=error.message)
    if isinstance(error, service.Locked):
        return HTTPException(status.HTTP_409_CONFLICT, detail=error.message)
    if isinstance(error, service.Invalid):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.message)
    raise error


@router.get(
    "/classes/{class_id}/exam-registrations",
    response_model=ClassExamRegistrationsOut,
    summary="Đăng ký thi tốt nghiệp của lớp 12: môn tự chọn từng em và trạng thái khóa (GVCN, BGH)",
)
def class_exam_registrations(
    class_id: int, user: CurrentUser, session: DbSession
) -> ClassExamRegistrationsOut:
    try:
        return service.get_registrations(session, user, class_id)
    except service.NotFound as error:
        raise _http(error) from None


@router.put(
    "/classes/{class_id}/exam-registrations/students/{student_id}",
    response_model=ClassExamRegistrationsOut,
    summary="Đặt lại 2 môn tự chọn của một học sinh (chỉ GVCN, lớp chưa khóa)",
)
def set_electives(
    class_id: int, student_id: int, body: ElectivesIn, user: CurrentUser, session: DbSession
) -> ClassExamRegistrationsOut:
    try:
        return service.set_electives(session, user, class_id, student_id, body)
    except (service.NotFound, service.Locked, service.Invalid) as error:
        raise _http(error) from None


@router.post(
    "/classes/{class_id}/exam-registrations/lock",
    response_model=ClassExamRegistrationsOut,
    summary="GVCN chốt (khóa) đăng ký thi của lớp để tránh sửa nhầm",
)
def lock_exam_registrations(
    class_id: int, user: CurrentUser, session: DbSession
) -> ClassExamRegistrationsOut:
    try:
        return service.lock(session, user, class_id)
    except (service.NotFound, service.Invalid) as error:
        raise _http(error) from None


@router.post(
    "/classes/{class_id}/exam-registrations/unlock",
    response_model=ClassExamRegistrationsOut,
    summary="GVCN mở khóa đăng ký thi của lớp để sửa lại",
)
def unlock_exam_registrations(
    class_id: int, user: CurrentUser, session: DbSession
) -> ClassExamRegistrationsOut:
    try:
        return service.unlock(session, user, class_id)
    except (service.NotFound, service.Invalid) as error:
        raise _http(error) from None
