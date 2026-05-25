import json
import os
from functools import lru_cache
from typing import Any

from app.schemas.question import Question


def _as_list(value) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
        return [value]
    return [str(value)]


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/").lstrip("/")
    for prefix in ("edumath-agent/backend/data/", "backend/data/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return f"/api/media/{normalized}"


def _db_connect():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=2,
    )


def _is_usable_db_question(
    *,
    question_text: str | None,
    answer: str | None,
    solution: str | None,
    quality_label: str | None,
    metadata: dict[str, Any] | None,
) -> bool:
    if not question_text or not question_text.strip():
        return False
    metadata = metadata or {}
    if metadata.get("review_status") in {
        "bad_split_cross_page",
        "incomplete_question",
        "exclude_from_recommendation",
    }:
        return False
    return True


def _row_to_question(row) -> Question | None:
    knowledge_points = row[4] or []
    if isinstance(knowledge_points, str):
        try:
            knowledge_points = json.loads(knowledge_points)
        except json.JSONDecodeError:
            knowledge_points = [knowledge_points]
    quality_label = row[7] or ""
    options = row[8] or []
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except json.JSONDecodeError:
            options = []
    metadata = row[9] or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not _is_usable_db_question(
        question_text=row[1],
        answer=row[2],
        solution=row[3],
        quality_label=quality_label,
        metadata=metadata,
    ):
        return None

    image_paths = _as_list(metadata.get("image_paths"))
    image_descriptions = _as_list(metadata.get("image_descriptions"))
    page_image_path = metadata.get("page_image_path")
    image_urls = [url for path in image_paths if (url := _media_url(path))]
    return Question(
        id=f"db:{row[0]}",
        question_text=row[1],
        answer=row[2],
        solution=row[3],
        knowledge_points=knowledge_points,
        difficulty=row[5],
        question_type=row[6],
        quality_label=quality_label,
        options=_as_list(options),
        common_mistakes=[],
        image_paths=image_paths,
        image_urls=image_urls,
        image_descriptions=image_descriptions,
        page_image_path=page_image_path,
        page_image_url=_media_url(page_image_path),
    )


@lru_cache(maxsize=1)
def load_all_questions() -> list[Question]:
    """Load all questions from PostgreSQL."""
    try:
        conn = _db_connect()
    except Exception:
        return []

    questions: list[Question] = []
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, question_text, COALESCE(answer, ''), COALESCE(solution, ''),
                       knowledge_points, COALESCE(difficulty, 'unknown'),
                       COALESCE(question_type, 'extracted'),
                       COALESCE(quality_label, ''), COALESCE(options, '[]'::jsonb), metadata
                FROM question_items
                WHERE question_text IS NOT NULL
                  AND length(trim(question_text)) > 0
                  AND COALESCE(quality_label, '') NOT IN ('low', 'pending_review')
                  AND (
                    COALESCE(answer, '') <> ''
                    OR COALESCE(solution, '') <> ''
                  )
                ORDER BY created_at DESC
                LIMIT 2000
                """
            )
            for row in cur.fetchall():
                question = _row_to_question(row)
                if question:
                    questions.append(question)
    return questions


def get_question(question_id: str) -> Question | None:
    candidates = {question_id}
    if question_id.startswith("db:"):
        candidates.add(question_id[3:])
    else:
        candidates.add(f"db:{question_id}")
    return next((item for item in load_all_questions() if item.id in candidates), None)


def search_questions(
    keyword: str | None = None,
    knowledge_point: str | None = None,
    difficulty: str | None = None,
    quality_label: str | None = None,
    has_answer: bool | None = True,
    has_solution: bool | None = True,
    limit: int = 100,
    offset: int = 0,
) -> list[Question]:
    keyword = keyword.strip() if keyword else None
    knowledge_point = knowledge_point.strip() if knowledge_point else None
    difficulty = difficulty.strip() if difficulty else None
    quality_label = quality_label.strip() if quality_label else None

    try:
        conn = _db_connect()
    except Exception:
        return []

    where = [
        "question_text IS NOT NULL",
        "length(trim(question_text)) > 0",
        "COALESCE(metadata ->> 'review_status', '') NOT IN ('bad_split_cross_page', 'incomplete_question', 'exclude_from_recommendation')",
    ]
    params: list[Any] = []
    if quality_label:
        where.append("quality_label = %s")
        params.append(quality_label)
    else:
        where.append("COALESCE(quality_label, '') NOT IN ('low', 'pending_review')")
    if has_answer is True:
        where.append("COALESCE(answer, '') <> ''")
    if has_solution is True:
        where.append("COALESCE(solution, '') <> ''")
    if keyword:
        where.append(
            """
            (
              question_text ILIKE %s
              OR answer ILIKE %s
              OR solution ILIKE %s
              OR knowledge_points::text ILIKE %s
            )
            """
        )
        like = f"%{keyword}%"
        params.extend([like, like, like, like])
    if knowledge_point:
        where.append("knowledge_points::text ILIKE %s")
        params.append(f"%{knowledge_point}%")
    if difficulty:
        where.append("difficulty = %s")
        params.append(difficulty)

    params.extend([limit, offset])
    sql = f"""
        SELECT id::text, question_text, COALESCE(answer, ''), COALESCE(solution, ''),
               knowledge_points, COALESCE(difficulty, 'unknown'),
               COALESCE(question_type, 'extracted'),
               COALESCE(quality_label, ''), COALESCE(options, '[]'::jsonb), metadata
        FROM question_items
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    questions: list[Question] = []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                for row in cur.fetchall():
                    question = _row_to_question(row)
                    if question:
                        questions.append(question)
    except Exception:
        return []
    return questions
