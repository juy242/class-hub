"""Bảng khóa ("đã chốt") đăng ký thi tốt nghiệp theo lớp + 4 hành động nhật ký mới (D-128).

- `exam_registration_locks`: có dòng cho một lớp = GVCN đã chốt; khi đó API chặn mọi sửa đăng ký cho
  tới khi GVCN tự mở (xóa dòng). Khóa theo lớp nên `class_id` làm khóa chính.
- `audit_logs.action` là VARCHAR + CHECK (D-025). Thêm 4 hành động mới (`view/edit/lock/unlock_
  exam_registration`) nên nới độ dài cột 20 → 24 (`unlock_exam_registration` dài 24) và thêm vào
  CHECK. Tên ràng buộc qua op.f() vì naming_convention của Base.metadata.

Revision ID: e7c2f9a5b3d1
Revises: b4d8f1c3a2e9
Create Date: 2026-11-10 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c2f9a5b3d1"
down_revision: str | Sequence[str] | None = "b4d8f1c3a2e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_ACTIONS = (
    "view_exam_registration",
    "edit_exam_registration",
    "lock_exam_registration",
    "unlock_exam_registration",
)
OLD_ACTIONS = (
    "view_class_students",
    "view_student_profile",
    "view_class_dashboard",
    "view_subject_scores",
    "import_confirm",
    "view_class_alerts",
    "view_school_alerts",
    "update_alert",
    "upload_regulation",
    "update_regulation",
    "create_user",
    "import_users",
    "update_user",
    "reset_user_password",
    "change_password",
    "update_school_year",
    "create_class",
    "update_class",
    "delete_class",
    "set_assignment",
    "remove_assignment",
    "remove_class_student",
    "generate_report",
    "edit_report",
    "approve_report",
    "export_report",
    "view_class_reports",
    "edit_scores",
    "view_class_conduct",
    "edit_conduct",
    "view_attendance",
    "edit_attendance",
    "view_lessons",
    "edit_lesson",
)
OLD_MAX_LEN = 20  # max len của OLD_ACTIONS ("remove_class_student")
NEW_MAX_LEN = 24  # max len khi có NEW_ACTIONS ("unlock_exam_registration")


def _replace_action_check(actions: Sequence[str]) -> None:
    values = ", ".join(f"'{action}'" for action in actions)
    op.drop_constraint(op.f("ck_audit_logs_action"), "audit_logs", type_="check")
    op.create_check_constraint(op.f("ck_audit_logs_action"), "audit_logs", f"action IN ({values})")


def upgrade() -> None:
    op.alter_column(
        "audit_logs",
        "action",
        existing_type=sa.String(length=OLD_MAX_LEN),
        type_=sa.String(length=NEW_MAX_LEN),
        existing_nullable=False,
    )
    _replace_action_check((*OLD_ACTIONS, *NEW_ACTIONS))

    op.create_table(
        "exam_registration_locks",
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"],
            ["classes.id"],
            name=op.f("fk_exam_registration_locks_class_id_classes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["locked_by"],
            ["users.id"],
            name=op.f("fk_exam_registration_locks_locked_by_users"),
        ),
        sa.PrimaryKeyConstraint("class_id", name=op.f("pk_exam_registration_locks")),
    )


def downgrade() -> None:
    op.drop_table("exam_registration_locks")
    # Xóa dòng nhật ký dùng hành động mới để khôi phục được CHECK và độ dài cột cũ.
    audit_logs = sa.table("audit_logs", sa.column("action", sa.String))
    op.execute(audit_logs.delete().where(audit_logs.c.action.in_(NEW_ACTIONS)))
    _replace_action_check(OLD_ACTIONS)
    op.alter_column(
        "audit_logs",
        "action",
        existing_type=sa.String(length=NEW_MAX_LEN),
        type_=sa.String(length=OLD_MAX_LEN),
        existing_nullable=False,
    )
