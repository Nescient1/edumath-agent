import { http } from './http'
import type { SimilarQuestion } from './diagnose'

export interface Question extends SimilarQuestion {
  answer: string
  solution: string
  common_mistakes: string[]
}

export function fetchQuestions(params: {
  keyword?: string
  knowledge_point?: string
  difficulty?: string
  quality_label?: string
  has_answer?: boolean
  has_solution?: boolean
  limit?: number
  offset?: number
}) {
  return http.get<SimilarQuestion[]>('/questions', { params })
}

export function fetchQuestionDetail(questionId: string) {
  return http.get<Question>(`/questions/${questionId}`)
}
