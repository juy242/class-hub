import type { ClassOverview } from '../../api/analytics'

// Thứ tự lớp trên biểu đồ khối (BGH). 'name': theo tên lớp. 'attention': lớp "cần chú ý" nhất của
// chính biểu đồ đó xếp trước. Chỉ đổi thứ tự hiển thị, không đụng vào số liệu (D-117).
export type ClassOrder = 'name' | 'attention'

// Mỗi biểu đồ có một thước đo "cần chú ý" riêng: tỉ lệ nhóm đáng lo trên sĩ số của lớp.
export type AttentionMetric = 'learning' | 'attention' | 'conduct' | 'promotion'

function rate(count: number, total: number): number {
  return total > 0 ? count / total : 0
}

// Thứ tự tự nhiên để 10A2 đứng trước 10A10 (không phải so chuỗi).
function byName(a: ClassOverview, b: ClassOverview): number {
  return a.name.localeCompare(b.name, 'vi', { numeric: true, sensitivity: 'base' })
}

// Tổng 3 chỉ số vẽ trên biểu đồ "cần quan tâm" (khớp CHART_INDICATORS trong GradeInsights): học tập
// Chưa đạt, có môn điểm quá thấp, nghỉ quá số buổi.
function attentionSum(item: ClassOverview): number {
  return (
    (item.learning_levels.fail ?? 0) + item.below_fail_students + item.absent_over_limit_students
  )
}

function attentionValue(item: ClassOverview, metric: AttentionMetric): number {
  switch (metric) {
    case 'learning':
      return rate(item.learning_levels.fail ?? 0, item.student_count)
    case 'conduct':
      return rate(item.conduct_levels.fail ?? 0, item.student_count)
    case 'promotion':
      return rate(item.promotion?.not_eligible ?? 0, item.student_count)
    case 'attention':
      return rate(attentionSum(item), item.student_count)
  }
}

// Trả về bản sao đã sắp xếp. "Cần chú ý" xếp theo tỉ lệ nặng nhất của biểu đồ, đồng hạng thì theo tên.
export function orderClasses(
  classes: ClassOverview[],
  order: ClassOrder,
  metric: AttentionMetric = 'learning',
): ClassOverview[] {
  if (order === 'name') return [...classes].sort(byName)
  return [...classes].sort((a, b) => {
    const diff = attentionValue(b, metric) - attentionValue(a, metric)
    return diff !== 0 ? diff : byName(a, b)
  })
}
