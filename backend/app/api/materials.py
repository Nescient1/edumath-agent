import json
import os

from fastapi import APIRouter, Query
from pydantic import BaseModel


router = APIRouter(tags=["materials"])


class MaterialChunkSummary(BaseModel):
    id: str
    title: str
    topic: str | None = None
    content_type: str
    section_type: str | None = None
    knowledge_points: list[str]
    quality_label: str | None = None
    preview: str


def _connect_pg():
    try:
        import psycopg
    except ImportError:
        return None
    try:
        return psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            connect_timeout=2,
        )
    except Exception:
        return None


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except json.JSONDecodeError:
            pass
        return [value]
    return [str(value)]


@router.get("/materials", response_model=list[MaterialChunkSummary])
def list_materials(
    knowledge_point: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    conn = _connect_pg()
    if conn is None:
        return []

    where = []
    params: list[object] = []
    if topic:
        where.append("d.topic = %s")
        params.append(topic)
    if knowledge_point:
        where.append("rc.knowledge_points::text LIKE %s")
        params.append(f"%{knowledge_point}%")

    where_sql = "WHERE " + " AND ".join(where) if where else ""
    sql = f"""
        SELECT rc.id::text, d.source_name, d.topic, rc.content_type, rc.section_type,
               rc.knowledge_points, rc.quality_label, left(rc.chunk_text, 260)
        FROM rag_chunks rc
        LEFT JOIN documents d ON d.id = rc.document_id
        {where_sql}
        ORDER BY rc.created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        MaterialChunkSummary(
            id=row[0],
            title=row[1] or "未命名资料",
            topic=row[2],
            content_type=row[3],
            section_type=row[4],
            knowledge_points=_as_list(row[5]),
            quality_label=row[6],
            preview=row[7] or "",
        )
        for row in rows
    ]
