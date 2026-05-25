import { http } from './http'

const RECOMMEND_HTTP_TIMEOUT_MS = 120_000

export interface GeneratedQuestion {
  question_text: string
  answer: string
  solution: string
  difficulty: string
  knowledge_points: string[]
  question_type: string
  source: string
}

export interface VariantResponse {
  questions: GeneratedQuestion[]
}

export function generateVariantQuestions(payload: {
  question_text: string
  knowledge_points: string[]
  difficulty?: string
  count?: number
}) {
  return http.post<VariantResponse>('/recommend/variants', payload, {
    timeout: RECOMMEND_HTTP_TIMEOUT_MS,
  })
}
