"""Dự báo điểm thi tốt nghiệp THPT cho học sinh khối 12 (D-123). Chỉ code tính (nguyên tắc 1).

KHÔNG phải công thức Thông tư 22 (nguyên tắc 2 nói riêng về Thông tư 22). Đây là một ước lượng
minh bạch, hồi quy ĐTB môn về một mức trung tâm (vì điểm thi chuẩn hoá thường sát mức chung hơn
điểm học ở lớp), kèm khoảng tin cậy ± để thể hiện độ không chắc chắn. Hệ số center/shrink/margin
đọc từ bảng `settings` (AnalyticsConfig), hiệu chỉnh được khi có dữ liệu điểm thi thật.

    điểm dự báo = center + shrink × (ĐTB − center)   (kẹp về [0; 10], làm tròn 1 chữ số thập phân)
    khoảng      = [điểm dự báo − margin ; điểm dự báo + margin]   (cũng kẹp về [0; 10])

Với center = 6,5, shrink = 0,85: ĐTB 9,0 → 8,6; ĐTB 4,0 → 4,4.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.analytics.config import AnalyticsConfig
from app.analytics.scores import round_score

ZERO = Decimal(0)
TEN = Decimal(10)


def _clamp(value: Decimal) -> Decimal:
    return max(ZERO, min(TEN, value))


@dataclass(frozen=True)
class ForecastBand:
    point: Decimal  # điểm dự báo, 1 chữ số thập phân, trong [0; 10]
    low: Decimal  # cận dưới của khoảng tin cậy
    high: Decimal  # cận trên của khoảng tin cậy


def forecast_band(average: Decimal, config: AnalyticsConfig) -> ForecastBand:
    """Dự báo điểm thi từ ĐTB môn (đã làm tròn). Hồi quy về trung bình + khoảng ±margin."""
    center = config.exam_forecast_center
    raw = center + config.exam_forecast_shrink * (average - center)
    point = _clamp(round_score(raw))
    margin = config.exam_forecast_margin
    return ForecastBand(
        point=point,
        low=_clamp(round_score(point - margin)),
        high=_clamp(round_score(point + margin)),
    )
