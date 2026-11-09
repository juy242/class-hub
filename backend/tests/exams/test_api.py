"""Đăng ký thi tốt nghiệp khối 12 (D-128): phân quyền 4 vai trò, validate môn tự chọn, khóa/mở.

Tài khoản seed: gvcn.12a2 chủ nhiệm 12A2; gv.van.12 dạy Ngữ văn khối 12 (GVBM của 12A2, không chủ
nhiệm); gv.toan.12 dạy Toán khối 12 và chủ nhiệm 12A1; bgh1 BGH; admin Admin. Mỗi HS khối 12 đã được
seed đăng ký Toán + Ngữ văn + 2 môn tự chọn.
"""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db

API = "/api/v1"
HOMEROOM = "gvcn.12a2@example.com"
LITERATURE = "gv.van.12@example.com"  # GVBM của 12A2 (môn Ngữ văn), không chủ nhiệm
MATH = "gv.toan.12@example.com"  # chủ nhiệm 12A1, dạy Toán ở 12A2
PRINCIPAL = "bgh1@example.com"
ADMIN = "admin@example.com"

Headers = Callable[[str], dict[str, str]]
Finder = Callable[[str], int]


def reg_url(class_id: int) -> str:
    return f"{API}/classes/{class_id}/exam-registrations"


def student_url(class_id: int, student_id: int) -> str:
    return f"{reg_url(class_id)}/students/{student_id}"


def lock_url(class_id: int) -> str:
    return f"{reg_url(class_id)}/lock"


def unlock_url(class_id: int) -> str:
    return f"{reg_url(class_id)}/unlock"


@pytest.fixture
def cls(class_id_of: Finder) -> int:
    return class_id_of("12A2")


# --- Phân quyền xem --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "status", "can_edit"),
    [
        (HOMEROOM, 200, True),
        (PRINCIPAL, 200, False),  # BGH xem được, không sửa
        (LITERATURE, 403, None),  # GVBM một môn: không quản lý đăng ký
        (MATH, 403, None),  # dạy Toán ở lớp này nhưng chủ nhiệm lớp khác
        (ADMIN, 403, None),  # admin không xem dữ liệu học sinh
    ],
)
def test_view_permissions(
    api_client: TestClient, auth_headers: Headers, cls: int, email: str, status: int, can_edit: bool
) -> None:
    response = api_client.get(reg_url(cls), headers=auth_headers(email))
    assert response.status_code == status
    if status == 200:
        assert response.json()["can_edit"] is can_edit


def test_grade_11_has_no_exam_registrations(
    api_client: TestClient, auth_headers: Headers, class_id_of: Finder
) -> None:
    eleven = class_id_of("11A2")
    response = api_client.get(reg_url(eleven), headers=auth_headers("gvcn.11a2@example.com"))
    assert response.status_code == 404


def test_shape(api_client: TestClient, auth_headers: Headers, cls: int) -> None:
    body = api_client.get(reg_url(cls), headers=auth_headers(HOMEROOM)).json()
    assert {s["name"] for s in body["compulsory"]} == {"Toán", "Ngữ văn"}
    assert body["elective_count"] == 2
    assert body["elective_options"]  # lớp có môn tự chọn hợp lệ
    assert body["locked"] is False
    assert len(body["students"]) == 40
    for student in body["students"]:
        assert len(student["elective_subject_ids"]) == 2
        assert student["complete"] is True


# --- Sửa môn tự chọn -------------------------------------------------------------------------


def test_homeroom_can_change_electives(
    api_client: TestClient, auth_headers: Headers, cls: int
) -> None:
    headers = auth_headers(HOMEROOM)
    body = api_client.get(reg_url(cls), headers=headers).json()
    options = [o["id"] for o in body["elective_options"]]
    student_id = body["students"][0]["student_id"]
    pick = options[:2]

    response = api_client.put(
        student_url(cls, student_id), headers=headers, json={"elective_subject_ids": pick}
    )
    assert response.status_code == 200
    row = next(s for s in response.json()["students"] if s["student_id"] == student_id)
    assert set(row["elective_subject_ids"]) == set(pick)
    assert row["complete"] is True


def test_edit_rejects_wrong_count(api_client: TestClient, auth_headers: Headers, cls: int) -> None:
    headers = auth_headers(HOMEROOM)
    body = api_client.get(reg_url(cls), headers=headers).json()
    options = [o["id"] for o in body["elective_options"]]
    student_id = body["students"][0]["student_id"]
    response = api_client.put(
        student_url(cls, student_id), headers=headers, json={"elective_subject_ids": options[:1]}
    )
    assert response.status_code == 422


def test_edit_rejects_compulsory_as_elective(
    api_client: TestClient, auth_headers: Headers, subject_id_of: Finder, cls: int
) -> None:
    headers = auth_headers(HOMEROOM)
    body = api_client.get(reg_url(cls), headers=headers).json()
    options = [o["id"] for o in body["elective_options"]]
    student_id = body["students"][0]["student_id"]
    # Toán là môn bắt buộc, không được chọn làm môn tự chọn.
    response = api_client.put(
        student_url(cls, student_id),
        headers=headers,
        json={"elective_subject_ids": [subject_id_of("Toán"), options[0]]},
    )
    assert response.status_code == 422


def test_principal_cannot_edit(api_client: TestClient, auth_headers: Headers, cls: int) -> None:
    body = api_client.get(reg_url(cls), headers=auth_headers(HOMEROOM)).json()
    options = [o["id"] for o in body["elective_options"]]
    student_id = body["students"][0]["student_id"]
    response = api_client.put(
        student_url(cls, student_id),
        headers=auth_headers(PRINCIPAL),
        json={"elective_subject_ids": options[:2]},
    )
    assert response.status_code == 403


# --- Khóa / mở -------------------------------------------------------------------------------


def test_lock_blocks_edit_then_unlock_allows(
    api_client: TestClient, auth_headers: Headers, cls: int
) -> None:
    headers = auth_headers(HOMEROOM)
    body = api_client.get(reg_url(cls), headers=headers).json()
    options = [o["id"] for o in body["elective_options"]]
    student_id = body["students"][0]["student_id"]
    payload = {"elective_subject_ids": options[:2]}

    locked = api_client.post(lock_url(cls), headers=headers)
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
    assert locked.json()["can_edit"] is False

    assert api_client.post(lock_url(cls), headers=headers).status_code == 422  # đã khóa rồi
    blocked = api_client.put(student_url(cls, student_id), headers=headers, json=payload)
    assert blocked.status_code == 409

    unlocked = api_client.post(unlock_url(cls), headers=headers)
    assert unlocked.status_code == 200
    assert unlocked.json()["locked"] is False

    assert api_client.post(unlock_url(cls), headers=headers).status_code == 422  # chưa khóa
    allowed = api_client.put(student_url(cls, student_id), headers=headers, json=payload)
    assert allowed.status_code == 200


@pytest.mark.parametrize("email", [PRINCIPAL, LITERATURE, MATH, ADMIN])
def test_only_homeroom_can_lock(
    api_client: TestClient, auth_headers: Headers, cls: int, email: str
) -> None:
    assert api_client.post(lock_url(cls), headers=auth_headers(email)).status_code == 403
