import { apiDownload, apiGet, apiPost, apiPut } from './client'
import type { Period } from './analytics'

// Khớp schema của back-end (backend/app/reports/schemas.py).
export type ReportType =
  | 'subject_comment'
  | 'school_record'
  | 'contact_slip'
  | 'report'
  | 'teaching_plan'
export type ReportScope = 'student' | 'class' | 'grade'
export type ReportStatus = 'draft' | 'approved'
export type JobStatus = 'running' | 'done' | 'stopped'

export interface StudentRef {
  id: number
  student_code: string
  full_name: string
}

export interface Report {
  id: number
  type: ReportType
  type_label: string
  scope: ReportScope
  semester: Period
  class_id: number | null
  subject_id: number | null
  target_id: number
  status: ReportStatus
  status_label: string
  text: string // bản đã duyệt nếu có, ngược lại là bản nháp
  needs_manual: boolean // AI chưa viết được bản đạt kiểm tra: giáo viên tự viết
  check_notes: string[] // mã vi phạm của lần sinh cuối
  attempts: number
  model: string | null
  created_at: string
  updated_at: string
  approved_at: string | null
  student: StudentRef | null
  warnings: string[] // cảnh báo kiểm tự động cho văn bản giáo viên sửa (không chặn)
}

export interface ReportJob {
  id: number
  class_id: number
  type: ReportType
  semester: Period
  subject_id: number | null
  status: JobStatus
  status_label: string
  total: number
  done: number
  needs_manual: number
  error_code: string | null
  created_at: string
  finished_at: string | null
}

// Tóm tắt số liệu của một học sinh để giáo viên có bối cảnh khi nhận xét (D-124). Mọi số do
// back-end tính qua Analytics; chỉ có với nhận xét học sinh (nhận xét môn / phiếu liên lạc / học bạ).
export interface ReportSummary {
  // Phiếu liên lạc / học bạ (GVCN):
  learning_level: string | null // 'good' | 'fair' | 'pass' | 'fail' | null
  conduct_level: string | null
  absent_total: number | null
  below_pass_count: number | null
  incomplete_count: number | null
  // Nhận xét môn (GVBM):
  subject_name: string | null
  average: number | null
  tx: number[] | null
  tx_missing: number | null
  midterm: number | null
  final: number | null
  comment_result: string | null // 'pass' | 'fail'
  complete: boolean | null
}

export interface ReportItem {
  student: StudentRef | null
  report: Report | null
  summary: ReportSummary | null
}

export interface ReportList {
  items: ReportItem[]
  job: ReportJob | null
}

// Giám sát tiến độ nhận xét của cả một khối, chỉ BGH xem (D-126). Chỉ số đếm, không tên học sinh.
export interface ReportProgress {
  written: number
  approved: number
  expected: number // số cần có (sĩ số với học bạ / phiếu liên lạc); 0 = không có mẫu số cố định
}

export interface ClassReportStatus {
  status: ReportStatus | null // null = chưa có
  status_label: string
  report_id: number | null
}

export interface ClassOversight {
  class_id: number
  class_name: string
  student_count: number
  school_record: ReportProgress
  contact_slip: ReportProgress
  subject_comment: ReportProgress
  class_report: ClassReportStatus
}

export interface GradeOversight {
  grade_level: number
  semester: Period
  classes: ClassOversight[]
}

export function fetchOversight(
  gradeLevel: number,
  semester: Period,
  schoolYearId: number | null,
  signal?: AbortSignal,
): Promise<GradeOversight> {
  const query = new URLSearchParams({ grade_level: String(gradeLevel), semester })
  if (schoolYearId != null) query.set('school_year_id', String(schoolYearId))
  return apiGet<GradeOversight>(`/reports/oversight?${query.toString()}`, signal)
}

// Bản nào, của lớp, môn, khối nào (hình dạng hợp lệ phụ thuộc loại, back-end kiểm lại).
export interface ReportTarget {
  type: ReportType
  semester: Period
  classId?: number
  subjectId?: number
  gradeLevel?: number
  // Năm học của báo cáo khối (D-113); null hoặc bỏ trống là năm hiện hành. Bản theo lớp dùng năm
  // của lớp nên không cần.
  schoolYearId?: number | null
}

function targetBody(target: ReportTarget): Record<string, unknown> {
  return {
    type: target.type,
    semester: target.semester,
    ...(target.classId !== undefined && { class_id: target.classId }),
    ...(target.subjectId !== undefined && { subject_id: target.subjectId }),
    ...(target.gradeLevel !== undefined && { grade_level: target.gradeLevel }),
    // Báo cáo khối (D-113) và báo cáo toàn trường (D-127) gắn với năm được chọn; bản theo lớp dùng
    // năm của lớp nên không gửi. Cả hai loại trên đều không có class_id.
    ...(target.classId === undefined &&
      target.schoolYearId != null && { school_year_id: target.schoolYearId }),
  }
}

export function fetchReports(target: ReportTarget, signal?: AbortSignal): Promise<ReportList> {
  const query = new URLSearchParams(
    Object.entries(targetBody(target)).map(([key, value]) => [key, String(value)]),
  )
  return apiGet<ReportList>(`/reports?${query.toString()}`, signal)
}

// Sinh một em hoặc một báo cáo lớp / khối ngay (back-end trả 201 kèm bản nháp).
export function generateReport(
  target: ReportTarget,
  options: { studentId?: number; feedback?: string } = {},
): Promise<Report> {
  return apiPost<Report>('/reports', {
    ...targetBody(target),
    ...(options.studentId !== undefined && { student_id: options.studentId }),
    ...(options.feedback && { feedback: options.feedback }),
  })
}

// Sinh nhận xét cho cả lớp: chạy nền, back-end trả 202 kèm công việc (tiến độ nằm trong danh sách).
export function startClassJob(target: ReportTarget): Promise<ReportJob> {
  return apiPost<ReportJob>('/reports', targetBody(target))
}

// Tạo một bản nháp RỖNG để giáo viên tự viết, KHÔNG gọi AI (dự phòng khi AI hết hạn mức). Back-end
// trả 201 kèm bản nháp (needs_manual = true, text rỗng) để mở thẳng ô soạn thảo.
export function createManualReport(
  target: ReportTarget,
  options: { studentId?: number } = {},
): Promise<Report> {
  return apiPost<Report>('/reports', {
    ...targetBody(target),
    manual: true,
    ...(options.studentId !== undefined && { student_id: options.studentId }),
  })
}

export function updateReport(
  reportId: number,
  body: { text?: string; approve?: boolean },
): Promise<Report> {
  return apiPut<Report>(`/reports/${reportId}`, body)
}

export function regenerateReport(reportId: number, feedback?: string): Promise<Report> {
  return apiPost<Report>(`/reports/${reportId}/regenerate`, feedback ? { feedback } : {})
}

// Tải PDF (chỉ bản đã duyệt) và cho trình duyệt lưu về máy.
export async function downloadReportPdf(reportId: number): Promise<void> {
  const { blob, filename } = await apiDownload(
    `/reports/${reportId}/export?format=pdf`,
    `bao-cao-${reportId}.pdf`,
  )
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Thu hồi sau một nhịp để trình duyệt kịp bắt đầu tải.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
