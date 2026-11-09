import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchExamRegistrations,
  lockExamRegistrations,
  setElectives,
  unlockExamRegistrations,
} from '../api/exams'
import type { ClassExamRegistrations } from '../api/exams'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'

function retry(failureCount: number, error: Error): boolean {
  return failureCount < 1 && !(error instanceof ApiError && error.status < 500)
}

export function useExamRegistrations(classId: number) {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['exam-registrations', token, classId],
    queryFn: ({ signal }) => fetchExamRegistrations(classId, signal),
    enabled: token !== null && Number.isInteger(classId),
    retry,
  })
}

// Mọi lệnh ghi (sửa môn, khóa, mở) trả về cả lớp sau khi ghi: cập nhật thẳng cache, và làm mới dự
// báo điểm thi vì đổi môn tự chọn làm đổi bảng dự báo.
export function useExamRegistrationActions(classId: number) {
  const { token } = useAuth()
  const client = useQueryClient()

  const apply = (data: ClassExamRegistrations) => {
    client.setQueryData(['exam-registrations', token, classId], data)
    void client.invalidateQueries({ queryKey: ['exam-forecast'] })
  }

  const editElectives = useMutation({
    mutationFn: ({ studentId, electiveSubjectIds }: { studentId: number; electiveSubjectIds: number[] }) =>
      setElectives(classId, studentId, electiveSubjectIds),
    onSuccess: apply,
  })
  const lock = useMutation({ mutationFn: () => lockExamRegistrations(classId), onSuccess: apply })
  const unlock = useMutation({
    mutationFn: () => unlockExamRegistrations(classId),
    onSuccess: apply,
  })

  return { editElectives, lock, unlock }
}
