import { apiGet, apiPost, apiPut } from './client'

// Đăng ký thi tốt nghiệp của lớp 12 (D-128). Số và quyền do back-end quyết; front-end chỉ hiển thị
// và gửi lựa chọn môn tự chọn.

export interface ExamSubjectRef {
  id: number
  name: string
}

export interface ExamStudentRegistration {
  student_id: number
  student_code: string
  full_name: string
  elective_subject_ids: number[]
  complete: boolean
}

export interface ClassExamRegistrations {
  class_info: { id: number; name: string; grade_level: number }
  can_manage: boolean
  can_edit: boolean
  locked: boolean
  locked_at: string | null
  locked_by: string | null
  elective_count: number
  compulsory: ExamSubjectRef[]
  elective_options: ExamSubjectRef[]
  students: ExamStudentRegistration[]
}

export function fetchExamRegistrations(classId: number, signal?: AbortSignal) {
  return apiGet<ClassExamRegistrations>(`/classes/${classId}/exam-registrations`, signal)
}

export function setElectives(classId: number, studentId: number, electiveSubjectIds: number[]) {
  return apiPut<ClassExamRegistrations>(
    `/classes/${classId}/exam-registrations/students/${studentId}`,
    { elective_subject_ids: electiveSubjectIds },
  )
}

export function lockExamRegistrations(classId: number) {
  return apiPost<ClassExamRegistrations>(`/classes/${classId}/exam-registrations/lock`, {})
}

export function unlockExamRegistrations(classId: number) {
  return apiPost<ClassExamRegistrations>(`/classes/${classId}/exam-registrations/unlock`, {})
}
