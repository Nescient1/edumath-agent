import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import PROJECT_ROOT, VECTOR_STORE_DIR, settings
from app.services.embedding_service import (
    ensure_compatible_vector_store,
    resolve_embeddings,
    write_embedding_config,
)


def connect_pg():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _json_list(value: Any) -> list[str]:
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
            return [value]
    return [str(value)]


def _metadata(**kwargs: Any) -> dict[str, str | int | float | bool]:
    result: dict[str, str | int | float | bool] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, list):
            result[key] = ", ".join(str(item) for item in value)
        else:
            result[key] = json.dumps(value, ensure_ascii=False)
    return result


def load_pg_documents(limit: int | None = None):
    from langchain_core.documents import Document

    docs: list[Document] = []
    ids: list[str] = []
    with connect_pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT rc.id::text, rc.chunk_text, rc.content_type, COALESCE(rc.section_type, ''),
                       rc.knowledge_points, COALESCE(rc.quality_label, ''),
                       COALESCE(d.source_name, ''), COALESCE(d.source_path, ''),
                       COALESCE(d.topic, ''), rc.metadata
                FROM rag_chunks rc
                LEFT JOIN documents d ON d.id = rc.document_id
                WHERE rc.chunk_text IS NOT NULL AND length(trim(rc.chunk_text)) > 0
                  AND COALESCE(rc.quality_label, '') NOT IN ('low')
                  AND COALESCE(rc.metadata->>'review_status', '') NOT IN (
                    'bad_split_cross_page',
                    'incomplete_question',
                    'exclude_from_recommendation'
                  )
                ORDER BY rc.created_at DESC
                {f'LIMIT {int(limit)}' if limit else ''}
                """
            )
            for row in cur.fetchall():
                knowledge_points = _json_list(row[4])
                metadata = row[9] or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                docs.append(
                    Document(
                        page_content=row[1],
                        metadata=_metadata(
                            source="postgres_rag_chunks",
                            title=row[6],
                            source_path=row[7],
                            content_type=row[2],
                            section_type=row[3],
                            knowledge_points=knowledge_points,
                            quality_label=row[5],
                            review_status=metadata.get("review_status"),
                            topic=row[8],
                            page_no=metadata.get("page_no"),
                            page_image_path=metadata.get("page_image_path"),
                        ),
                    )
                )
                ids.append(f"pg-rag-{row[0]}")

            cur.execute(
                f"""
                SELECT qi.id::text, qi.question_text, COALESCE(qi.answer, ''),
                       COALESCE(qi.solution, ''), qi.knowledge_points,
                       COALESCE(qi.difficulty, 'unknown'),
                       COALESCE(qi.question_type, 'extracted'),
                       COALESCE(qi.quality_label, ''),
                       COALESCE(d.source_name, ''), COALESCE(d.source_path, ''),
                       COALESCE(d.topic, ''), qi.metadata
                FROM question_items qi
                LEFT JOIN documents d ON d.id = qi.document_id
                WHERE qi.question_text IS NOT NULL AND length(trim(qi.question_text)) > 0
                  AND COALESCE(qi.quality_label, '') NOT IN ('low', 'pending_review')
                  AND (
                    COALESCE(qi.answer, '') <> ''
                    OR COALESCE(qi.solution, '') <> ''
                  )
                  AND COALESCE(qi.metadata->>'review_status', '') NOT IN (
                    'bad_split_cross_page',
                    'incomplete_question',
                    'exclude_from_recommendation'
                  )
                ORDER BY qi.created_at DESC
                {f'LIMIT {int(limit)}' if limit else ''}
                """
            )
            for row in cur.fetchall():
                knowledge_points = _json_list(row[4])
                metadata = row[11] or {}
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        metadata = {}
                content = "\n".join(
                    part
                    for part in [
                        f"题目：{row[1]}",
                        f"答案：{row[2]}" if row[2] else "",
                        f"解析：{row[3]}" if row[3] else "",
                    ]
                    if part
                )
                docs.append(
                    Document(
                        page_content=content,
                        metadata=_metadata(
                            source="postgres_question_items",
                            title=f"题目 {row[0]}",
                            source_path=row[9],
                            content_type="exercise",
                            section_type="question",
                            knowledge_points=knowledge_points,
                            difficulty=row[5],
                            question_type=row[6],
                            quality_label=row[7],
                            review_status=metadata.get("review_status"),
                            topic=row[10],
                            question_id=row[0],
                            page_no=metadata.get("page_no"),
                            page_image_path=metadata.get("page_image_path"),
                            image_paths=metadata.get("image_paths") or [],
                        ),
                    )
                )
                ids.append(f"pg-question-{row[0]}")

    return docs, ids


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Embed PostgreSQL rag_chunks/question_items into Chroma.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows from each table for testing.")
    parser.add_argument(
        "--use-openai-embedding",
        action="store_true",
        help="Use OPENAI_API_KEY for embeddings. Default uses local-bge/local-hash to avoid spending chat API quota.",
    )
    args = parser.parse_args()

    if not args.use_openai_embedding:
        settings.openai_api_key = ""
        os.environ["OPENAI_API_KEY"] = ""

    try:
        from langchain_chroma import Chroma
    except ImportError as exc:
        raise RuntimeError("Missing langchain-chroma dependency.") from exc

    embeddings, embedding_config = resolve_embeddings()
    ensure_compatible_vector_store(embedding_config, VECTOR_STORE_DIR)
    docs, ids = load_pg_documents(args.limit)
    if not docs:
        print("No PostgreSQL documents found to embed.")
        return 0

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    vector_store = Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=embeddings,
    )
    try:
        vector_store.delete(ids=ids)
    except Exception:
        pass
    vector_store.add_documents(docs, ids=ids)
    write_embedding_config(embedding_config, VECTOR_STORE_DIR)
    print(f"embedded_documents={len(docs)}")
    print(f"vector_store={VECTOR_STORE_DIR}")
    print(f"embedding_provider={embedding_config['provider']} model={embedding_config['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
