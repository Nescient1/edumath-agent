import { http } from './http'

/** OCR 含图片处理与可选 LLM 纠错，易超过默认 12s。 */
const OCR_HTTP_TIMEOUT_MS = 120_000

export interface OcrBlock {
  text: string
  confidence: number
}

export interface OcrResponse {
  ocr_text: string
  corrected_text?: string | null
  vision_text?: string | null
  blocks: OcrBlock[]
  pix2text_text?: string | null
  engine?: string | null
}

export interface PageQuestionCandidate {
  question_no: string
  question_text: string
  options: string[]
  answer: string
  solution: string
  confidence: 'high' | 'medium' | 'low' | string
}

export interface PageOcrResponse {
  page_text: string
  questions: PageQuestionCandidate[]
  engine?: string | null
  raw_text?: string | null
}

export function uploadOcrImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  return http.post<OcrResponse>('/ocr', formData, {
    timeout: OCR_HTTP_TIMEOUT_MS,
  })
}

export function uploadPageOcrImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  return http.post<PageOcrResponse>('/ocr/page', formData, {
    timeout: OCR_HTTP_TIMEOUT_MS,
  })
}
