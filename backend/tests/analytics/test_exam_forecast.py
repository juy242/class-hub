"""Dự báo điểm thi tốt nghiệp khối 12 (D-123): công thức hồi quy và phân quyền (chỉ GVCN và GVBM).

Tài khoản (xem README): gv.toan.12 chủ nhiệm 12A1; bgh1 là BGH; admin là Admin. Giáo viên bộ môn của
12A1 được tìm động để khỏi phụ thuộc phân công cụ thể của seed.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.config import AnalyticsConfig
from app.analytics.exam_forecast import forecast_band
from app.auth.models import AuditLog, User
from app.classes.academic import ExamRegistration
from app.classes.models import ClassStudent, SchoolClass, TeachingAssignment
from app.core.enums import AuditAction

API = "/api/v1"
Headers = Callable[[str], dict[str, str]]
ClassId = Callable[[str], int]


# --- Công thức (không cần DB) --------------------------------------------------------------------


def test_forecast_regresses_toward_center_with_a_band(config: AnalyticsConfig) -> None:
    # Mặc định center 6,5, shrink 0,85, margin 1,0: 6,5 + 0,85 × (8,6 − 6,5) = 8,285 → 8,3.
    band = forecast_band(Decimal("8.6"), config)
    assert (band.point, band.low, band.high) == (Decimal("8.3"), Decimal("7.3"), Decimal("9.3"))


def test_forecast_pulls_a_low_average_up_toward_center(config: AnalyticsConfig) -> None:
    # 6,5 + 0,85 × (4,0 − 6,5) = 4,375 → 4,4 (làm tròn nửa lên); điểm thi kém thường đỡ cực đoan.
    assert forecast_band(Decimal("4.0"), config).point == Decimal("4.4")


def test_forecast_band_is_clamped_to_0_and_10(
    make_config: Callable[..., AnalyticsConfig],
) -> None:
    config = make_config(exam_forecast_center=6.5, exam_forecast_shrink=1, exam_forecast_margin=3)
    assert forecast_band(Decimal("10"), config).high == Decimal("10")  # không vượt 10
    assert forecast_band(Decimal("1.0"), config).low == Decimal("0")  # không âm


# --- Phân quyền và nội dung (cần DB) -------------------------------------------------------------


def _subject_teacher_of(session: Session, class_id: int) -> tuple[User, str]:
    """Một GVBM dạy môn đăng ký thi ở lớp này nhưng KHÔNG phải GVCN (để kiểm lọc theo môn)."""
    homeroom = session.scalar(
        select(SchoolClass.homeroom_teacher_id).where(SchoolClass.id == class_id)
    )
    exam_subject_ids = set(
        session.scalars(
            select(ExamRegistration.subject_id)
            .join(ClassStudent, ClassStudent.id == ExamRegistration.class_student_id)
            .where(ClassStudent.class_id == class_id)
        )
    )
    row = session.execute(
        select(TeachingAssignment.teacher_id)
        .where(
            TeachingAssignment.class_id == class_id,
            TeachingAssignment.subject_id.in_(exam_subject_ids),
            TeachingAssignment.teacher_id != homeroom,
        )
        .limit(1)
    ).first()
    assert row is not None, "Seed phải có một GVBM dạy môn thi của 12A1 ngoài GVCN."
    teacher = session.get(User, row[0])
    assert teacher is not None
    return teacher, teacher.email


@pytest.mark.db
def test_homeroom_sees_every_registered_exam_subject(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId
) -> None:
    class_id = class_id_of("12A1")
    body: Any = api_client.get(
        f"{API}/classes/{class_id}/exam-forecast",
        headers=auth_headers("gv.toan.12@example.com"),
    ).json()

    assert body["is_grade12"] is True
    assert body["method"] == {"center": 6.5, "shrink": 0.85, "margin": 1.0}
    assert len(body["students"]) > 0
    student = body["students"][0]
    names = {f["subject_name"] for f in student["subjects"]}
    assert {"Toán", "Ngữ văn"} <= names  # hai môn bắt buộc đều được dự báo
    forecast = student["subjects"][0]
    assert set(forecast) == {
        "subject_id",
        "subject_name",
        "basis_average",
        "basis",
        "predicted",
        "low",
        "high",
    }
    assert forecast["low"] <= forecast["predicted"] <= forecast["high"]


@pytest.mark.db
def test_subject_teacher_sees_only_their_own_subject(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    class_id = class_id_of("12A1")
    _, email = _subject_teacher_of(db_session, class_id)
    body: Any = api_client.get(
        f"{API}/classes/{class_id}/exam-forecast", headers=auth_headers(email)
    ).json()

    subjects = {f["subject_name"] for st in body["students"] for f in st["subjects"]}
    assert len(subjects) == 1  # GVBM chỉ thấy đúng môn mình dạy
    assert len(body["students"]) > 0


@pytest.mark.db
@pytest.mark.parametrize("email", ["bgh1@example.com", "admin@example.com"])
def test_principal_and_admin_are_forbidden(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, email: str
) -> None:
    class_id = class_id_of("12A1")
    response = api_client.get(
        f"{API}/classes/{class_id}/exam-forecast", headers=auth_headers(email)
    )
    assert response.status_code == 403


@pytest.mark.db
def test_unauthenticated_is_401(api_client: TestClient, class_id_of: ClassId) -> None:
    class_id = class_id_of("12A1")
    assert api_client.get(f"{API}/classes/{class_id}/exam-forecast").status_code == 401


@pytest.mark.db
def test_non_grade_12_class_returns_an_empty_forecast(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId
) -> None:
    class_id = class_id_of("11A2")
    body: Any = api_client.get(
        f"{API}/classes/{class_id}/exam-forecast",
        headers=auth_headers("gvcn.11a2@example.com"),
    ).json()
    assert body["is_grade12"] is False
    assert body["students"] == []


@pytest.mark.db
def test_viewing_the_forecast_is_logged(
    api_client: TestClient, auth_headers: Headers, class_id_of: ClassId, db_session: Session
) -> None:
    class_id = class_id_of("12A1")
    api_client.get(
        f"{API}/classes/{class_id}/exam-forecast",
        headers=auth_headers("gv.toan.12@example.com"),
    )
    logged = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == AuditAction.VIEW_SUBJECT_SCORES, AuditLog.class_id == class_id
        )
    ).all()
    assert any(entry.details.get("view") == "exam_forecast" for entry in logged)
