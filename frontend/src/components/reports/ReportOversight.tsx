import type { ReactNode } from 'react'
import type { Period } from '../../api/analytics'
import type { ClassOversight, ClassReportStatus, ReportProgress } from '../../api/reports'
import { useOversight } from '../../hooks/useReports'
import { formatInt } from '../../lib/format'
import { QueryState } from '../QueryState'

// Bảng giám sát tiến độ nhận xét của cả một khối, chỉ BGH xem (D-126). Mỗi lớp một dòng: đã viết /
// đã duyệt học bạ, phiếu liên lạc, nhận xét môn, cùng trạng thái báo cáo lớp. Bấm tên lớp để mở
// thẳng phạm vi lớp đó (xem số liệu và báo cáo). Chỉ số đếm, không nêu tên học sinh nào.

function Th({ children, right = true }: { children: ReactNode; right?: boolean }) {
  return (
    <th scope="col" className={`px-3 py-2 font-medium ${right ? 'text-right' : ''}`}>
      {children}
    </th>
  )
}

function ProgressCell({ progress }: { progress: ReportProgress }) {
  const { written, approved, expected } = progress
  if (expected > 0) {
    // Học bạ / phiếu liên lạc: mẫu số là sĩ số.
    const done = approved === expected && expected > 0
    const pending = written - approved
    return (
      <td className="px-3 py-2 text-right tabular-nums">
        <span className={done ? 'text-emerald-700' : expected > 0 ? 'text-slate-700' : ''}>
          {formatInt(approved)}/{formatInt(expected)}
        </span>
        {pending > 0 && <span className="text-amber-700"> · {formatInt(pending)} nháp</span>}
      </td>
    )
  }
  // Nhận xét môn: không có mẫu số cố định, chỉ nêu đã viết và trong đó đã duyệt.
  if (written === 0) {
    return <td className="px-3 py-2 text-right tabular-nums text-slate-400">—</td>
  }
  return (
    <td className="px-3 py-2 text-right tabular-nums">
      {formatInt(approved)}/{formatInt(written)} duyệt
    </td>
  )
}

const STATUS_TONE: Record<string, string> = {
  approved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  draft: 'bg-amber-50 text-amber-800 ring-amber-200',
}

function ReportStatusCell({ status }: { status: ClassReportStatus }) {
  const tone =
    status.status === null ? 'bg-slate-50 text-slate-500 ring-slate-200' : STATUS_TONE[status.status]
  return (
    <td className="px-3 py-2 text-right">
      <span className={`rounded-lg px-2 py-0.5 text-xs ring-1 ${tone}`}>{status.status_label}</span>
    </td>
  )
}

interface OversightTableProps {
  classes: ClassOversight[]
  onOpenClass: (classId: number) => void
}

function OversightTable({ classes, onOpenClass }: OversightTableProps) {
  if (classes.length === 0) {
    return <p className="text-sm text-slate-500">Khối này chưa có lớp nào.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-max">
        <thead>
          <tr>
            <Th right={false}>Lớp</Th>
            <Th>Sĩ số</Th>
            <Th>Học bạ</Th>
            <Th>Phiếu liên lạc</Th>
            <Th>Nhận xét môn</Th>
            <Th>Báo cáo lớp</Th>
          </tr>
        </thead>
        <tbody>
          {classes.map((item) => (
            <tr key={item.class_id}>
              <th scope="row" className="px-3 py-2 font-normal whitespace-nowrap">
                <button
                  type="button"
                  onClick={() => onOpenClass(item.class_id)}
                  className="font-medium text-brand-700 hover:underline"
                >
                  {item.class_name}
                </button>
              </th>
              <td className="px-3 py-2 text-right tabular-nums">{formatInt(item.student_count)}</td>
              <ProgressCell progress={item.school_record} />
              <ProgressCell progress={item.contact_slip} />
              <ProgressCell progress={item.subject_comment} />
              <ReportStatusCell status={item.class_report} />
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        Học bạ và phiếu liên lạc hiển thị <strong>đã duyệt / sĩ số</strong>; nhận xét môn hiển thị đã
        duyệt trên số đã viết (nhiều môn nên không có mẫu số cố định). Bấm tên lớp để xem số liệu và
        báo cáo của lớp.
      </p>
    </div>
  )
}

interface ReportOversightProps {
  grade: number
  period: Period
  schoolYearId: number | null
  onOpenClass: (classId: number) => void
}

export function ReportOversight({ grade, period, schoolYearId, onOpenClass }: ReportOversightProps) {
  const oversight = useOversight(grade, period, schoolYearId)
  return (
    <QueryState query={oversight}>
      {(data) => <OversightTable classes={data.classes} onOpenClass={onOpenClass} />}
    </QueryState>
  )
}
