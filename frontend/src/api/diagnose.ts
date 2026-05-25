import { http } from './http'

/** 诊断/批改会走 RAG + LLM，后端单次 LLM 可达约 60s，默认 axios 12s 会误报“无法连接”。 */
const DIAGNOSE_HTTP_TIMEOUT_MS = 120_000

export interface SimilarQuestion {
  id: string
  question_text: string
  knowledge_points: string[]
  difficulty: string
  question_type: string
  options?: string[]
  quality_label?: string
  image_urls?: string[]
  image_descriptions?: string[]
}

export interface SourceSummary {
  title: string
  source: string
  content_type: string
  score: number
}

export interface StepExplanation {
  step_number: number
  title: string
  content: string
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
  step_by_step_explanation?: StepExplanation[] | null
  general_strategy?: string | null
  common_pitfalls?: string[] | null
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

export interface PracticeAssistResponse {
  question_id: string
  mode: 'grade' | 'hint' | 'answer' | 'solution' | string
  message: string
  next_step?: string | null
  score?: number | null
  is_correct?: boolean | null
  feedback?: string | null
  reference_answer?: string | null
  solution?: string | null
  matched_keywords: string[]
  missed_keywords: string[]
  knowledge_points: string[]
  attempt_id?: string | null
  can_show_answer: boolean
}

export function diagnoseWrongQuestion(payload: DiagnosePayload) {
  return http.post<DiagnoseResponse>('/diagnose', payload, {
    timeout: DIAGNOSE_HTTP_TIMEOUT_MS,
  })
}

export function gradePracticeAnswer(payload: {
  student_id: string
  question_id: string
  student_answer: string
}) {
  return http.post<PracticeGradeResponse>('/practice/grade', payload, {
    timeout: DIAGNOSE_HTTP_TIMEOUT_MS,
  })
}

export function assistPractice(payload: {
  student_id: string
  question_id: string
  student_input?: string
  mode?: 'auto' | 'grade' | 'hint' | 'answer' | 'solution'
  recognized_answer?: string | null
  ocr_image_path?: string | null
}) {
  return http.post<PracticeAssistResponse>('/practice/assist', payload, {
    timeout: DIAGNOSE_HTTP_TIMEOUT_MS,
  })
}
