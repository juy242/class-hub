import type { ExamForecastMethod, ExamSubjectForecast } from '../../api/analytics'
import { useExamForecast } from '../../hooks/useAnalytics'
import { formatScore } from '../../lib/format'
import { Panel } from '../Panel'
import { QueryState } from '../QueryState'

// Dự báo điểm thi tốt nghiệp (khối 12, D-123). Chỉ GVCN và GVBM mới gọi (back-end chặn BGH/Admin).
// Là ước lượng từ ĐTB (hồi quy về trung bình) kèm khoảng ±, KHÔNG phải điểm thi thật.

const BASIS_LABEL: Record<ExamSubjectForecast['basis'], string> = {
  year: 'cả năm',
  semester1: 'HK I',
  semester2: 'HK II',
}

function PredictedCell({ forecast }: { forecast: ExamSubjectForecast }) {
  return (
    <span className="tabular-nums">
      <span className="font-semibold">{formatScore(forecast.predicted)}</span>
      <span className="ml-1 text-xs text-slate-500">
        ({formatScore(forecast.low)}–{formatScore(forecast.high)})
      </span>
    </span>
  )
}

function MethodNote({ method }: { method: ExamForecastMethod }) {
  return (
    <p className="mt-3 text-xs text-slate-500">
      Dự báo là ước lượng từ ĐTB (hồi quy về mức trung tâm {formatScore(method.center)}), không phải
      điểm thi thật; số trong ngoặc là khoảng dao động ±{formatScore(method.margin)}. Dùng để tham
      khảo, lập kế hoạch ôn tập.
    </p>
  )
}

// Trên trang Bảng điểm môn: dự báo của riêng môn đang xem, cho từng học sinh đăng ký thi môn đó.
export function SubjectExamForecast({ classId, subjectId }: { classId: number; subjectId: number }) {
  const forecast = useExamForecast(classId)
  return (
    <Panel
      id="du-bao-thi-tn"
      title="Dự báo điểm thi tốt nghiệp"
      description="Chỉ giáo viên chủ nhiệm và giáo viên bộ môn xem được. Ước lượng từ ĐTB, không phải điểm thi thật."
    >
      <QueryState query={forecast}>
        {(data) => {
          const rows = data.students
            .map((student) => ({
              student,
              forecast: student.subjects.find((s) => s.subject_id === subjectId),
            }))
            .filter((row): row is { student: (typeof row)['student']; forecast: ExamSubjectForecast } =>
              row.forecast !== undefined,
            )
          if (rows.length === 0) {
            return (
              <p className="text-sm text-slate-600">
                Chưa có học sinh nào đăng ký thi tốt nghiệp môn này, hoặc chưa đủ điểm để dự báo.
              </p>
            )
          }
          return (
            <>
              <div className="overflow-x-auto">
                <table className="data-table min-w-max">
                  <thead>
                    <tr>
                      <th scope="col" className="px-2 py-2 font-medium">
                        STT
                      </th>
                      <th scope="col" className="px-2 py-2 font-medium">
                        Mã HS
                      </th>
                      <th scope="col" className="px-2 py-2 font-medium">
                        Họ và tên
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-medium">
                        ĐTB dùng để dự báo
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-medium">
                        Điểm thi dự báo
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ student, forecast: f }, index) => (
                      <tr key={student.student_id}>
                        <td className="px-2 py-1.5 text-slate-500">{index + 1}</td>
                        <td className="px-2 py-1.5 font-mono">{student.student_code}</td>
                        <th scope="row" className="px-2 py-1.5 font-normal">
                          {student.full_name}
                        </th>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                          {formatScore(f.basis_average)}{' '}
                          <span className="text-xs text-slate-500">({BASIS_LABEL[f.basis]})</span>
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <PredictedCell forecast={f} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <MethodNote method={data.method} />
            </>
          )
        }}
      </QueryState>
    </Panel>
  )
}

// Trên hồ sơ học sinh lớp 12: dự báo mọi môn em đăng ký thi (GVBM chỉ thấy môn mình dạy).
export function StudentExamForecast({ classId, studentId }: { classId: number; studentId: number }) {
  const forecast = useExamForecast(classId)
  return (
    <Panel
      id="du-bao-thi-tn"
      title="Dự báo điểm thi tốt nghiệp"
      description="Chỉ giáo viên chủ nhiệm và giáo viên bộ môn xem được. Ước lượng từ ĐTB, không phải điểm thi thật."
    >
      <QueryState query={forecast}>
        {(data) => {
          const mine = data.students.find((student) => student.student_id === studentId)
          if (!mine || mine.subjects.length === 0) {
            return (
              <p className="text-sm text-slate-600">
                Em này chưa đăng ký thi tốt nghiệp, hoặc chưa đủ điểm để dự báo.
              </p>
            )
          }
          return (
            <>
              <div className="overflow-x-auto">
                <table className="data-table min-w-max">
                  <thead>
                    <tr>
                      <th scope="col" className="px-2 py-2 font-medium">
                        Môn thi
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-medium">
                        ĐTB dùng để dự báo
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-medium">
                        Điểm thi dự báo
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {mine.subjects.map((f) => (
                      <tr key={f.subject_id}>
                        <th scope="row" className="px-2 py-1.5 font-normal">
                          {f.subject_name}
                        </th>
                        <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                          {formatScore(f.basis_average)}{' '}
                          <span className="text-xs text-slate-500">({BASIS_LABEL[f.basis]})</span>
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <PredictedCell forecast={f} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <MethodNote method={data.method} />
            </>
          )
        }}
      </QueryState>
    </Panel>
  )
}
