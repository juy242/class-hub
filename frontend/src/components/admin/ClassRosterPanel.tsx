import { useState } from 'react'
import { useClassRoster } from '../../hooks/useAdmin'
import { QueryState } from '../QueryState'

// Ngày sinh từ back-end là chuỗi "YYYY-MM-DD" (chỉ ngày): đổi sang "dd/mm/yyyy" không qua Date để
// khỏi lệch múi giờ. Giá trị lạ hoặc null thì hiện "—".
function formatBirthday(iso: string | null): string {
  if (!iso) return '—'
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!match) return iso
  const [, year, month, day] = match
  return `${day}/${month}/${year}`
}

interface ClassRosterPanelProps {
  classId: number
  className: string
}

// Danh sách định danh học sinh của lớp cho Admin (D-122): chỉ mã, họ tên, ngày sinh để phân biệt
// học sinh. Không có thông tin phụ huynh, không có điểm hay dữ liệu học tập.
export function ClassRosterPanel({ classId, className }: ClassRosterPanelProps) {
  const roster = useClassRoster(classId)
  const [keyword, setKeyword] = useState('')

  return (
    <QueryState query={roster}>
      {(data) => {
        const needle = keyword.trim().toLowerCase()
        const rows = needle
          ? data.students.filter(
              (student) =>
                student.student_code.toLowerCase().includes(needle) ||
                student.full_name.toLowerCase().includes(needle),
            )
          : data.students

        if (data.students.length === 0) {
          return (
            <p className="text-sm text-slate-600">
              Lớp {className} chưa có học sinh. Nhập danh sách ở phần bên dưới.
            </p>
          )
        }

        return (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-600">
                {data.students.length} học sinh
                {needle && ` · ${rows.length} khớp "${keyword.trim()}"`}
              </p>
              <input
                type="search"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="Tìm theo mã hoặc họ tên…"
                aria-label={`Tìm học sinh lớp ${className}`}
                className="input w-full max-w-xs"
              />
            </div>
            <div className="overflow-x-auto">
              <table className="data-table min-w-max">
                <thead>
                  <tr>
                    <th scope="col" className="py-2 pr-4 text-right font-medium">
                      STT
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Mã HS
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Họ và tên
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Ngày sinh
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 align-middle">
                  {rows.map((student, index) => (
                    <tr key={student.student_code}>
                      <td className="py-2 pr-4 text-right tabular-nums text-slate-500">
                        {index + 1}
                      </td>
                      <td className="px-3 py-2 font-mono text-sm tabular-nums">
                        {student.student_code}
                      </td>
                      <td className="px-3 py-2">{student.full_name}</td>
                      <td className="px-3 py-2 tabular-nums">
                        {formatBirthday(student.date_of_birth)}
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-center text-sm text-slate-500">
                        Không có học sinh nào khớp.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )
      }}
    </QueryState>
  )
}
