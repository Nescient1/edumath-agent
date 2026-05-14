# Data Schema

## Knowledge Point

Stored in `data/knowledge_points.json`.

- `id`
- `name`
- `chapter`
- `description`
- `prerequisites`
- `common_exam_methods`
- `keywords`

## Question

Stored in `data/questions.json`.

- `id`
- `question_text`
- `answer`
- `solution`
- `knowledge_points`
- `difficulty`
- `question_type`
- `common_mistakes`

## Runtime Profile

Generated in `backend/storage/profiles.json`.

- `student_id`
- `grade`
- `target_score`
- `weak_points`
- `error_types`
- `total_wrong_questions`
- `updated_at`

## Wrong Record

Generated in `backend/storage/wrong_records.json`.

- `id`
- `student_id`
- `question_text`
- `student_answer`
- `knowledge_points`
- `error_type`
- `diagnosis`
- `created_at`
