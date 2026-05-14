# API Design

Base URL: `http://127.0.0.1:8000/api`

## OCR

`POST /ocr`

Multipart form field:

- `file`: PNG / JPG / JPEG / BMP / WEBP image

Response:

```json
{
  "ocr_text": "识别后的完整文本",
  "blocks": [
    {
      "text": "单行识别结果",
      "confidence": 0.98
    }
  ]
}
```

## Health

`GET /health`

Returns service status.

## Questions

`GET /questions`

Query params:

- `keyword`
- `knowledge_point`
- `difficulty`

`GET /questions/{question_id}`

Returns one question with answer and solution.

## Diagnose

`POST /diagnose`

```json
{
  "student_id": "S001",
  "question_text": "已知函数 f(x)=x^3-3x，求函数的单调区间和极值。",
  "student_answer": "我只求了导数，不知道后面怎么做。"
}
```

Returns knowledge points, error type, explanation, retrieved note snippets, and similar questions.

## Recommend

`POST /recommend`

```json
{
  "knowledge_points": ["导数与函数单调性"],
  "difficulty": "基础",
  "count": 3
}
```

## Profile

`GET /profile/{student_id}`

`GET /profile/{student_id}/records`

## Practice

`POST /practice/grade`

```json
{
  "student_id": "S001",
  "question_id": "Q002",
  "student_answer": "先求导..."
}
```
