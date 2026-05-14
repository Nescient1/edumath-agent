import { http } from './http'

export interface WeakPoint {
  name: string
  count: number
}

export interface StudentProfile {
  student_id: string
  grade: string
  target_score: number
  weak_points: WeakPoint[]
  error_types: Record<string, number>
  total_wrong_questions: number
  recommendation: string
  updated_at?: string | null
}

export interface WrongQuestionRecord {
  id: string
  student_id: string
  question_text: string
  student_answer?: string | null
  knowledge_points: string[]
  error_type: string
  diagnosis: string
  created_at: string
}

export function fetchProfile(studentId: string) {
  return http.get<StudentProfile>(`/profile/${studentId}`)
}

export function fetchWrongRecords(studentId: string) {
  return http.get<WrongQuestionRecord[]>(`/profile/${studentId}/records`)
}
