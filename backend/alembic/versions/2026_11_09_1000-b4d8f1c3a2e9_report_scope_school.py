"""Thêm phạm vi 'school' cho báo cáo toàn trường của BGH (D-127).

`scope` là VARCHAR + CHECK (D-025, không dùng enum gốc của PostgreSQL), nên chỉ cần thay ràng buộc
CHECK để cho thêm giá trị 'school' — không cần ALTER TYPE. 'school' (6 ký tự) ngắn hơn 'student'
(7) nên độ dài cột giữ nguyên.

Revision ID: b4d8f1c3a2e9
Revises: c1a4e7b9d2f6
Create Date: 2026-11-09 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d8f1c3a2e9"
down_revision: str | Sequence[str] | None = "c1a4e7b9d2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = ("student", "class", "grade")
_NEW = ("student", "class", "grade", "school")


def _recreate(values: Sequence[str]) -> None:
    # SQL thẳng để quy ước đặt tên của metadata không thêm tiền tố "ck_reports_" lần nữa.
    allowed = ", ".join(f"'{value}'" for value in values)
    op.execute("ALTER TABLE reports DROP CONSTRAINT ck_reports_scope")
    op.execute(f"ALTER TABLE reports ADD CONSTRAINT ck_reports_scope CHECK (scope IN ({allowed}))")


def upgrade() -> None:
    _recreate(_NEW)


def downgrade() -> None:
    _recreate(_OLD)
