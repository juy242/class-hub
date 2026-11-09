import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import type { ClassExamRegistrations, ExamStudentRegistration, ExamSubjectRef } from '../api/exams'
import { ApiError } from '../api/client'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useExamRegistrations, useExamRegistrationActions } from '../hooks/useExams'

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ.'
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('vi-VN')
}

// Một dòng học sinh: giữ lựa chọn tại chỗ; khi đã chọn đúng số môn và khác cũ thì lưu ngay. Key của
// dòng gồm danh sách môn từ máy chủ nên sau khi lưu xong dòng tự dựng lại theo dữ liệu mới.
function StudentRow({
  index,
  student,
  options,
  electiveCount,
  canEdit,
  saving,
  onSave,
}: {
  index: number
  student: ExamStudentRegistration
  options: ExamSubjectRef[]
  electiveCount: number
  canEdit: boolean
  saving: boolean
  onSave: (electiveSubjectIds: number[]) => void
}) {
  const [selected, setSelected] = useState<number[]>(student.elective_subject_ids)
  const full = selected.length >= electiveCount

  function toggle(subjectId: number) {
    const next = selected.includes(subjectId)
      ? selected.filter((id) => id !== subjectId)
      : [...selected, subjectId]
    setSelected(next)
    const changed =
      next.length !== student.elective_subject_ids.length ||
      next.some((id) => !student.elective_subject_ids.includes(id))
    if (next.length === electiveCount && changed) onSave(next)
  }

  return (
    <tr>
      <td className="px-2 py-1.5 text-slate-500">{index + 1}</td>
      <td className="px-2 py-1.5 font-mono">{student.student_code}</td>
      <th scope="row" className="px-2 py-1.5 font-normal">
        {student.full_name}
      </th>
      {options.map((option) => {
        const checked = selected.includes(option.id)
        return (
          <td key={option.id} className="px-2 py-1.5 text-center">
            <input
              type="checkbox"
              aria-label={`${student.full_name} – ${option.name}`}
              checked={checked}
              disabled={!canEdit || saving || (!checked && full)}
              onChange={() => toggle(option.id)}
            />
          </td>
        )
      })}
      <td className="px-2 py-1.5 text-right whitespace-nowrap">
        {saving ? (
          <span className="text-xs text-slate-500">Đang lưu…</span>
        ) : selected.length === electiveCount ? (
          <span className="text-xs font-medium text-green-700">Đủ {electiveCount} môn</span>
        ) : (
          <span className="text-xs font-medium text-amber-700">
            Chọn {electiveCount - selected.length} môn nữa
          </span>
        )}
      </td>
    </tr>
  )
}

function LockBar({ data, classId }: { data: ClassExamRegistrations; classId: number }) {
  const { lock, unlock } = useExamRegistrationActions(classId)
  const error = lock.error ?? unlock.error
  const busy = lock.isPending || unlock.isPending

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-sm text-slate-700">
          {data.locked ? (
            <>
              <span className="font-semibold text-slate-900">Đã chốt.</span> Khóa lúc{' '}
              {data.locked_at ? formatDateTime(data.locked_at) : '—'}
              {data.locked_by ? ` bởi ${data.locked_by}` : ''}. Không sửa được cho tới khi mở khóa.
            </>
          ) : (
            <>
              <span className="font-semibold text-slate-900">Chưa chốt.</span> Sửa xong hãy khóa để
              tránh thao tác nhầm; cần đổi môn thì mở khóa rồi sửa lại.
            </>
          )}
        </p>
        {data.can_manage &&
          (data.locked ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => unlock.mutate()}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-100 disabled:opacity-60"
            >
              Mở khóa để sửa
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => lock.mutate()}
              className="rounded-lg border border-brand-700 bg-brand-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-800 disabled:opacity-60"
            >
              Chốt (khóa) đăng ký
            </button>
          ))}
      </div>
      {error !== null && (
        <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
          {errorText(error)}
        </p>
      )}
    </div>
  )
}

function Registrations({ data, classId }: { data: ClassExamRegistrations; classId: number }) {
  const { editElectives } = useExamRegistrationActions(classId)
  const savingStudent =
    editElectives.isPending && editElectives.variables ? editElectives.variables.studentId : null
  const compulsory = useMemo(() => data.compulsory.map((s) => s.name).join(' · '), [data.compulsory])

  return (
    <div className="space-y-4">
      <LockBar data={data} classId={classId} />
      <Panel
        id="dang-ky-thi-tn"
        title="Môn tự chọn của từng học sinh"
        description={`Môn bắt buộc (mọi em đều thi): ${compulsory}. Mỗi em chọn đúng ${data.elective_count} môn tự chọn trong các môn dưới đây.${data.can_edit ? '' : data.locked ? ' Đang khóa — mở khóa để sửa.' : ' Chỉ GVCN của lớp sửa được.'}`}
      >
        {editElectives.error !== null && (
          <p
            role="alert"
            className="mb-3 rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200"
          >
            {errorText(editElectives.error)}
          </p>
        )}
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
                {data.elective_options.map((option) => (
                  <th key={option.id} scope="col" className="px-2 py-2 text-center font-medium">
                    {option.name}
                  </th>
                ))}
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  Trạng thái
                </th>
              </tr>
            </thead>
            <tbody>
              {data.students.map((student, index) => (
                <StudentRow
                  key={`${student.student_id}-${student.elective_subject_ids.join(',')}-${data.locked}`}
                  index={index}
                  student={student}
                  options={data.elective_options}
                  electiveCount={data.elective_count}
                  canEdit={data.can_edit}
                  saving={savingStudent === student.student_id}
                  onSave={(electiveSubjectIds) =>
                    editElectives.mutate({ studentId: student.student_id, electiveSubjectIds })
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

// Trang GVCN quản lý đăng ký thi tốt nghiệp của lớp 12 (D-128); BGH xem được, không sửa. Chỉ đổi môn
// tự chọn — Toán, Ngữ văn luôn bắt buộc. Mọi quyền và ràng buộc do back-end kiểm lại.
export default function ExamRegistrationsPage() {
  const classId = Number(useParams().classId)
  const query = useExamRegistrations(classId)
  const name = query.data?.class_info.name

  return (
    <>
      <PageTitle
        title={name ? `Đăng ký thi tốt nghiệp · lớp ${name}` : 'Đăng ký thi tốt nghiệp'}
        subtitle="Môn thi tốt nghiệp của học sinh khối 12"
      />
      <QueryState query={query}>
        {(data) => <Registrations data={data} classId={classId} />}
      </QueryState>
    </>
  )
}
