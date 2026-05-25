import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import BACKEND_DIR, PROJECT_ROOT


OUTPUT_ROOT = BACKEND_DIR / "data" / "llm_processed" / "function_derivative"


def connect_pg():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def load_local_page_results() -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for path in OUTPUT_ROOT.rglob("page_result.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        data["_path"] = str(path.relative_to(PROJECT_ROOT))
        pages.append(data)
    return pages


def db_summary() -> dict[str, Any]:
    try:
        conn = connect_pg()
    except Exception as exc:
        return {"db_available": False, "error": str(exc)}

    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM documents WHERE source_category = 'lecture'")
            documents = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM text_blocks")
            text_blocks = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM rag_chunks")
            rag_chunks = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM question_items")
            question_items = cur.fetchone()[0]
            cur.execute(
                """
                SELECT count(*)
                FROM question_items
                WHERE jsonb_array_length(COALESCE(metadata->'image_paths', '[]'::jsonb)) > 0
                """
            )
            questions_with_images = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COALESCE(quality_label, 'unknown'), count(*)
                FROM text_blocks
                GROUP BY COALESCE(quality_label, 'unknown')
                ORDER BY 2 DESC
                """
            )
            text_block_quality = dict(cur.fetchall())
            cur.execute(
                """
                SELECT COALESCE(quality_label, 'unknown'), count(*)
                FROM question_items
                GROUP BY COALESCE(quality_label, 'unknown')
                ORDER BY 2 DESC
                """
            )
            question_quality = dict(cur.fetchall())

    return {
        "db_available": True,
        "documents": documents,
        "text_blocks": text_blocks,
        "rag_chunks": rag_chunks,
        "question_items": question_items,
        "questions_with_images": questions_with_images,
        "text_block_quality": text_block_quality,
        "question_quality": question_quality,
    }


def build_report() -> dict[str, Any]:
    pages = load_local_page_results()
    llm_status = Counter(page.get("llm", {}).get("status", "unknown") for page in pages)
    vision_status = Counter(page.get("vision", {}).get("status", "unknown") for page in pages)
    pix2text_status = Counter(page.get("pix2text", {}).get("status", "unknown") for page in pages)
    question_items = sum(
        len((page.get("llm", {}).get("result") or {}).get("question_items") or [])
        for page in pages
    )
    figures = sum(len(page.get("figures", []) or []) for page in pages)
    figures_with_description = sum(
        1
        for page in pages
        for figure in page.get("figures", []) or []
        if figure.get("description")
    )
    quality = Counter(
        (page.get("llm", {}).get("result") or {}).get("quality_label", "unknown")
        for page in pages
    )

    return {
        "local_output_root": str(OUTPUT_ROOT.relative_to(PROJECT_ROOT)),
        "local_pages": len(pages),
        "local_llm_status": dict(llm_status),
        "local_vision_status": dict(vision_status),
        "local_pix2text_status": dict(pix2text_status),
        "local_quality_labels": dict(quality),
        "local_extracted_question_items": question_items,
        "local_figure_candidates": figures,
        "local_figures_with_description": figures_with_description,
        "database": db_summary(),
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    db = report["database"]
    lines = [
        "# EduMath Function/Derivative Ingest Quality Report",
        "",
        f"- Local pages: {report['local_pages']}",
        f"- Local LLM status: `{report['local_llm_status']}`",
        f"- Local Vision status: `{report['local_vision_status']}`",
        f"- Local Pix2Text status: `{report['local_pix2text_status']}`",
        f"- Local quality labels: `{report['local_quality_labels']}`",
        f"- Local extracted question items: {report['local_extracted_question_items']}",
        f"- Local figure candidates: {report['local_figure_candidates']}",
        f"- Local figures with description: {report['local_figures_with_description']}",
        "",
        "## Database",
        "",
    ]
    if db.get("db_available"):
        lines.extend(
            [
                f"- Documents: {db['documents']}",
                f"- Text blocks: {db['text_blocks']}",
                f"- RAG chunks: {db['rag_chunks']}",
                f"- Question items: {db['question_items']}",
                f"- Questions with images: {db['questions_with_images']}",
                f"- Text block quality: `{db['text_block_quality']}`",
                f"- Question quality: `{db['question_quality']}`",
            ]
        )
    else:
        lines.append(f"- Database unavailable: {db.get('error')}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Report quality metrics for function/derivative ingestion.")
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "docs" / "function_derivative_ingest_quality_report.md"),
        help="Markdown report output path.",
    )
    args = parser.parse_args()
    report = build_report()
    output = Path(args.output)
    write_markdown(report, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
