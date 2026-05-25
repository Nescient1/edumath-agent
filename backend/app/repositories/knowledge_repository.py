import json
import os
from functools import lru_cache

from app.schemas.question import KnowledgePoint


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


@lru_cache(maxsize=1)
def load_knowledge_points() -> list[KnowledgePoint]:
    """Load knowledge points from PostgreSQL. Falls back to empty list."""
    try:
        conn = _db_connect()
    except Exception:
        return []

    points: list[KnowledgePoint] = []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, name, chapter, description,
                           COALESCE(prerequisites, '[]'::jsonb),
                           COALESCE(common_exam_methods, '[]'::jsonb),
                           COALESCE(keywords, '[]'::jsonb)
                    FROM knowledge_points
                    ORDER BY id
                    """
                )
                for row in cur.fetchall():
                    points.append(
                        KnowledgePoint(
                            id=row[0],
                            name=row[1],
                            chapter=row[2] or "",
                            description=row[3] or "",
                            prerequisites=_as_list(row[4]),
                            common_exam_methods=_as_list(row[5]),
                            keywords=_as_list(row[6]),
                        )
                    )
    except Exception:
        return []
    return points


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except json.JSONDecodeError:
            pass
        return [value] if value.strip() else []
    return []
