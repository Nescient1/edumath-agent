import { http } from './http'

export interface WeakPoint {
  name: string
  count: number
}

export interface ProfileAdviceItem {
  title: string
  action: string
}

export interface ProfileWeeklyTask {
  day: string
  task: string
}

export interface ProfileAdvice {
  summary: string
  priority_points: string[]
  mistake_advice: ProfileAdviceItem[]
  weekly_plan: ProfileWeeklyTask[]
  generated_at?: string | null
}

export interface StudentProfile {
  student_id: string
  name: string
  grade: string
  target_score: number
  current_score?: number | null
  textbook_version: string
  current_topic: string
  learning_goal: string
  weak_points: WeakPoint[]
  error_types: Record<string, number>
  mastery: Record<string, number | string | boolean>
  total_wrong_questions: number
  recommendation: string
  llm_advice?: string | null
  advice?: ProfileAdvice | null
  updated_at?: string | null
}

export interface StudentProfileUpdate {
  name?: string
  grade?: string
  target_score?: number
  current_score?: number | null
  textbook_version?: string
  current_topic?: string
  learning_goal?: string
  weak_points?: WeakPoint[]
  error_types?: Record<string, number>
}

export interface WrongQuestionRecord {
  id: string
  student_id: string
  question_text: string
  student_answer?: string | null
  knowledge_points: string[]
  error_type: string
  diagnosis: string
  review_status: string
  is_mastered: boolean
  created_at: string
  updated_at?: string | null
}

export function fetchProfile(studentId: string) {
  return http.get<StudentProfile>(`/profile/${studentId}`)
}

export function updateProfile(studentId: string, data: StudentProfileUpdate) {
  return http.put<StudentProfile>(`/profile/${studentId}`, data)
}

export function refreshProfileAdvice(studentId: string) {
  return http.post<ProfileAdvice>(`/profile/${studentId}/advice`)
}

export function fetchWrongRecords(
  studentId: string,
  params?: { limit?: number; offset?: number },
) {
  return http.get<WrongQuestionRecord[]>(`/profile/${studentId}/records`, { params })
}

export function updateWrongRecord(
  studentId: string,
  recordId: string,
  data: { review_status?: string; is_mastered?: boolean },
) {
  return http.patch<WrongQuestionRecord>(
    `/profile/${studentId}/records/${recordId}`,
    data,
  )
}
