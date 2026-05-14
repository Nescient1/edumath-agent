import { http } from './http'

export interface OcrBlock {
  text: string
  confidence: number
}

export interface OcrResponse {
  ocr_text: string
  blocks: OcrBlock[]
}

export function uploadOcrImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  return http.post<OcrResponse>('/ocr', formData)
}
