import { useMemo, type ReactNode } from 'react'
import type { Dashboard, GradeOverview, Period } from '../../api/analytics'
import { useDashboard, useGradeOverview } from '../../hooks/useAnalytics'
import { formatInt, formatScore } from '../../lib/format'
import { LEVEL_LABELS } from '../../lib/labels'
import { QueryState } from '../QueryState'

// Số liệu tổng hợp đặt ngay cạnh báo cáo của BGH (D-125): để Ban giám hiệu có bối cảnh khi đọc và
// duyệt bản AI, không phải sinh bản mới hay sang màn hình khác mới thấy con số. Mọi số do back-end
// tính sẵn (build_grade_overview / build_dashboard) — giao diện chỉ bày lại, không tính thêm.

const LEVELS = ['good', 'fair', 'pass', 'fail', 'incomplete'] as const

function Th({ children, right = true }: { children: ReactNode; right?: boolean }) {
  return (
    <th scope="col" className={`px-3 py-2 font-medium ${right ? 'text-right' : ''}`}>
      {children}
    </th>
  )
}

// --- Cả khối: mỗi lớp một dòng, kèm bảng ĐTB từng môn ---------------------------------------------

function GradeTable({ overview }: { overview: GradeOverview }) {
  const scoreSubjects = overview.subjects.filter((s) => s.assessment_type === 'score')
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="data-table min-w-max">
          <thead>
            <tr>
              <Th right={false}>Lớp</Th>
              <Th>Sĩ số</Th>
              {LEVELS.map((level) => (
                <Th key={level}>{LEVEL_LABELS[level]}</Th>
              ))}
              <Th>Nghỉ nhiều</Th>
              <Th>Nghỉ quá phép</Th>
              <Th>Có môn quá thấp</Th>
            </tr>
          </thead>
          <tbody>
            {overview.classes.map((item) => (
              <tr key={item.class_id}>
                <th scope="row" className="px-3 py-2 font-normal whitespace-nowrap">
                  {item.name}
                </th>
                <td className="px-3 py-2 text-right tabular-nums">{formatInt(item.student_count)}</td>
                {LEVELS.map((level) => (
                  <td key={level} className="px-3 py-2 text-right tabular-nums">
                    {formatInt(item.learning_levels[level] ?? 0)}
                  </td>
                ))}
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatInt(item.absent_notice_students)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-red-700">
                  {formatInt(item.absent_over_limit_students)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-amber-700">
                  {formatInt(item.below_fail_students)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {scoreSubjects.length > 0 && overview.classes.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm font-medium text-slate-600 hover:text-slate-800">
            ĐTB trung bình từng môn theo lớp
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="data-table min-w-max">
              <thead>
                <tr>
                  <Th right={false}>Môn</Th>
                  {overview.classes.map((c) => (
                    <Th key={c.class_id}>{c.name}</Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {scoreSubjects.map((subject) => {
                  const meanOf = new Map(subject.class_means.map((m) => [m.class_id, m.mean]))
                  return (
                    <tr key={subject.subject_id}>
                      <th scope="row" className="px-3 py-2 font-normal whitespace-nowrap">
                        {subject.name}
                      </th>
                      {overview.classes.map((c) => (
                        <td key={c.class_id} className="px-3 py-2 text-right tabular-nums">
                          {meanOf.has(c.class_id) ? formatScore(meanOf.get(c.class_id) ?? null) : '—'}
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}

// --- Một lớp: phân bố học lực, hạnh kiểm, nghỉ học và ĐTB từng môn --------------------------------

function Distribution({ title, counts }: { title: string; counts: Record<string, number> }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-slate-500">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {LEVELS.map((level) => {
          const value = counts[level] ?? 0
          if (value === 0) return null
          const tone =
            level === 'fail'
              ? 'bg-red-50 text-red-700 ring-red-200'
              : level === 'incomplete'
                ? 'bg-slate-50 text-slate-500 ring-slate-200'
                : 'bg-slate-50 text-slate-700 ring-slate-200'
          return (
            <span
              key={level}
              className={`rounded-lg px-2 py-0.5 text-xs ring-1 ${tone}`}
            >
              {LEVEL_LABELS[level]} <strong className="tabular-nums">{formatInt(value)}</strong>
            </span>
          )
        })}
      </div>
    </div>
  )
}

function ClassTable({ dashboard }: { dashboard: Dashboard }) {
  const scoreSubjects = useMemo(
    () => dashboard.subjects.filter((s) => s.assessment_type === 'score'),
    [dashboard.subjects],
  )
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Sĩ số <strong className="tabular-nums">{formatInt(dashboard.student_count)}</strong> · Nghỉ
        nhiều <strong className="tabular-nums">{formatInt(dashboard.absent_notice_students)}</strong>{' '}
        · Nghỉ quá phép{' '}
        <strong className="tabular-nums text-red-700">
          {formatInt(dashboard.absent_over_limit_students)}
        </strong>
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Distribution title="Học lực" counts={dashboard.learning_levels} />
        <Distribution title="Hạnh kiểm" counts={dashboard.conduct_levels} />
      </div>
      {scoreSubjects.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm font-medium text-slate-600 hover:text-slate-800">
            ĐTB từng môn
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="data-table min-w-max">
              <thead>
                <tr>
                  <Th right={false}>Môn</Th>
                  <Th>ĐTB</Th>
                  <Th>Dưới mức đạt</Th>
                  <Th>Thiếu dữ liệu</Th>
                </tr>
              </thead>
              <tbody>
                {scoreSubjects.map((subject) => (
                  <tr key={subject.subject_id}>
                    <th scope="row" className="px-3 py-2 font-normal whitespace-nowrap">
                      {subject.name}
                    </th>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatScore(subject.mean)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-amber-700">
                      {formatInt(subject.below_pass)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-500">
                      {formatInt(subject.incomplete)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  )
}

// --- Khối dùng ở trang báo cáo của BGH -----------------------------------------------------------

export function GradeFigures({ grade, period }: { grade: number; period: Period }) {
  const overview = useGradeOverview(grade, period)
  return (
    <QueryState query={overview}>{(data) => <GradeTable overview={data} />}</QueryState>
  )
}

export function ClassFigures({ classId, period }: { classId: number; period: Period }) {
  const dashboard = useDashboard(classId, period)
  return (
    <QueryState query={dashboard}>{(data) => <ClassTable dashboard={data} />}</QueryState>
  )
}
