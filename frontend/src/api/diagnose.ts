import { http } from './http'

export interface SimilarQuestion {
  id: string
  question_text: string
  knowledge_points: string[]
  difficulty: string
  question_type: string
}

export interface SourceSummary {
  title: string
  source: string
  content_type: string
  score: number
}

export interface DiagnoseResponse {
  record_id: string
  intent: string
  answer_mode: string
  retrieval_quality: string
  knowledge_points: string[]
  difficulty: string
  error_type: string
  diagnosis: string
  explanation: string
  key_concepts: string[]
  retrieved_context: string[]
  source_summary: SourceSummary[]
  similar_questions: SimilarQuestion[]
}

export interface DiagnosePayload {
  student_id: string
  question_text: string
  student_answer?: string
}

export interface PracticeGradeResponse {
  question_id: string
  score: number
  is_correct: boolean
  feedback: string
  reference_answer: string
  matched_keywords: string[]
  missed_keywords: string[]
  knowledge_points: string[]
}

export function diagnoseWrongQuestion(payload: DiagnosePayload) {
  return http.post<DiagnoseResponse>('/diagnose', payload)
}

export function gradePracticeAnswer(payload: {
  student_id: string
  question_id: string
  student_answer: string
}) {
  return http.post<PracticeGradeResponse>('/practice/grade', payload)
}
