import { http } from './http'

const LEARNING_PATH_TIMEOUT_MS = 120_000

export interface LearningPathTask {
  day: number
  knowledge_point: string
  task_type: string
  questions: string[]
  description: string
}

export interface LearningPathMilestone {
  day: number
  description: string
  checkpoints: string[]
}

export interface LearningPath {
  student_id: string
  priority_order: string[]
  daily_tasks: LearningPathTask[]
  milestones: LearningPathMilestone[]
  estimated_days: number
  generated_at: string
  source: string
}

export function fetchLearningPath(studentId: string) {
  return http.get<LearningPath>(`/profile/${studentId}/learning-path`, {
    timeout: LEARNING_PATH_TIMEOUT_MS,
  })
}
