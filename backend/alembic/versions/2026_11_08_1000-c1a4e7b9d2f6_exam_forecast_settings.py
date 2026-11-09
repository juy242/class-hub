"""Hệ số dự báo điểm thi tốt nghiệp (khối 12) trong bảng settings (D-123).

Ba khoá cho công thức hồi quy ĐTB về trung bình + khoảng ± (app/analytics/exam_forecast.py). Không
phải công thức Thông tư 22; là ước lượng để GVCN/GVBM tham khảo, Admin hiệu chỉnh được sau này.

Revision ID: c1a4e7b9d2f6
Revises: e7b2c9d4f1a6
Create Date: 2026-11-08 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a4e7b9d2f6"
down_revision: str | Sequence[str] | None = "e7b2c9d4f1a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SETTINGS = [
    {
        "key": "exam_forecast_center",
        "value": 6.5,
        "description": (
            "Dự báo điểm thi tốt nghiệp: mức trung tâm mà ĐTB được kéo về (điểm thi chuẩn hoá "
            "thường sát mức chung hơn điểm ở lớp). Hiệu chỉnh khi có dữ liệu điểm thi thật."
        ),
    },
    {
        "key": "exam_forecast_shrink",
        "value": 0.85,
        "description": (
            "Dự báo điểm thi tốt nghiệp: hệ số co (0 đến 1). Điểm dự báo = center + shrink × "
            "(ĐTB − center). Càng nhỏ càng kéo mạnh về mức trung tâm."
        ),
    },
    {
        "key": "exam_forecast_margin",
        "value": 1.0,
        "description": (
            "Dự báo điểm thi tốt nghiệp: nửa độ rộng khoảng tin cậy (± điểm) quanh điểm dự báo, "
            "thể hiện độ không chắc chắn."
        ),
    },
]

settings_table = sa.table(
    "settings",
    sa.column("key", sa.String),
    sa.column("value", postgresql.JSONB),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(settings_table, SETTINGS)


def downgrade() -> None:
    """Downgrade schema."""
    keys = [row["key"] for row in SETTINGS]
    op.execute(settings_table.delete().where(settings_table.c.key.in_(keys)))
