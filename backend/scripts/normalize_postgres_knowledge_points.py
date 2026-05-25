import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
ALIASES_PATH = BACKEND_DIR / "data" / "knowledge_point_aliases.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "postgres_knowledge_point_normalization_report.md"


def connect_pg():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        return [value.strip()] if value.strip() else []
    return [str(value).strip()] if str(value).strip() else []


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def canonicalize(point: str, aliases: dict[str, str]) -> str:
    point = point.strip()
    if not point:
        return ""
    if point in aliases:
        return aliases[point]
    compact = compact_text(point)
    for alias, canonical in aliases.items():
        if compact == compact_text(alias):
            return canonical
    return point


def normalize_points(value: Any, aliases: dict[str, str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for point in as_list(value):
        canonical = canonicalize(point, aliases)
        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)
    return normalized


def fetch_rows(cur, table: str) -> list[tuple[str, Any]]:
    cur.execute(f"SELECT id::text, knowledge_points FROM {table}")
    return cur.fetchall()


def update_table(cur, table: str, aliases: dict[str, str], *, apply: bool) -> tuple[int, int]:
    changed = 0
    total = 0
    for row_id, points in fetch_rows(cur, table):
        total += 1
        old_points = as_list(points)
        new_points = normalize_points(points, aliases)
        if old_points == new_points:
            continue
        changed += 1
        if apply:
            cur.execute(
                f"UPDATE {table} SET knowledge_points = %s::jsonb WHERE id = %s",
                (json.dumps(new_points, ensure_ascii=False), row_id),
            )
    return total, changed


def collect_point_counts(cur, table: str) -> list[tuple[str, int]]:
    cur.execute(
        f"""
        SELECT value, count(*)
        FROM {table}, jsonb_array_elements_text(knowledge_points) AS value
        GROUP BY value
        ORDER BY count(*) DESC, value
        LIMIT 80
        """
    )
    return [(str(value), int(count)) for value, count in cur.fetchall()]


def collect_duplicate_questions(cur) -> list[tuple[str, int, list[str]]]:
    cur.execute("SELECT id::text, question_text FROM question_items")
    grouped: dict[str, list[str]] = defaultdict(list)
    for row_id, question_text in cur.fetchall():
        key = compact_text(question_text)
        if len(key) >= 16:
            grouped[key].append(row_id)
    duplicates = [
        (key[:80], len(ids), ids[:8])
        for key, ids in grouped.items()
        if len(ids) > 1
    ]
    duplicates.sort(key=lambda item: item[1], reverse=True)
    return duplicates[:50]


def write_report(
    *,
    apply: bool,
    table_results: dict[str, tuple[int, int]],
    question_counts: list[tuple[str, int]],
    rag_counts: list[tuple[str, int]],
    duplicates: list[tuple[str, int, list[str]]],
) -> None:
    lines = [
        "# PostgreSQL Knowledge Point Normalization Report",
        "",
        f"- Mode: {'apply' if apply else 'dry-run'}",
        "",
        "## Updated Tables",
        "",
    ]
    for table, (total, changed) in table_results.items():
        lines.append(f"- `{table}`: scanned {total}, changed {changed}")

    lines.extend(["", "## Top Question Knowledge Points", ""])
    for point, count in question_counts:
        lines.append(f"- {point}: {count}")

    lines.extend(["", "## Top RAG Knowledge Points", ""])
    for point, count in rag_counts:
        lines.append(f"- {point}: {count}")

    lines.extend(["", "## Exact Duplicate Question Candidates", ""])
    if not duplicates:
        lines.append("- None")
    else:
        for preview, count, ids in duplicates:
            lines.append(f"- count={count}, ids={', '.join(ids)}")
            lines.append(f"  - preview: `{preview}`")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize PostgreSQL knowledge point JSONB arrays and report exact duplicate questions."
    )
    parser.add_argument("--apply", action="store_true", help="Write normalized knowledge points to PostgreSQL.")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    table_results: dict[str, tuple[int, int]] = {}

    with connect_pg() as conn:
        with conn.cursor() as cur:
            for table in ("question_items", "rag_chunks"):
                table_results[table] = update_table(cur, table, aliases, apply=args.apply)
            if args.apply:
                conn.commit()
            question_counts = collect_point_counts(cur, "question_items")
            rag_counts = collect_point_counts(cur, "rag_chunks")
            duplicates = collect_duplicate_questions(cur)

    write_report(
        apply=args.apply,
        table_results=table_results,
        question_counts=question_counts,
        rag_counts=rag_counts,
        duplicates=duplicates,
    )
    for table, (total, changed) in table_results.items():
        print(f"{table}: scanned={total} changed={changed}")
    print(f"report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
