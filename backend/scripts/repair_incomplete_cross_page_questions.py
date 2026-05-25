import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import PROJECT_ROOT


REPORT_PATH = PROJECT_ROOT / "docs" / "cross_page_question_repair_report.md"
INCOMPLETE_STATUS = "bad_split_cross_page"


def connect_pg():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _compact(text: str | None) -> str:
    return re.sub(r"\s+", "", text or "")


def _preview(text: str | None, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _page_no(metadata: dict[str, Any], fallback: Any = None) -> int | None:
    value = metadata.get("page_no", fallback)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_part_one_only(text: str) -> bool:
    compact = _compact(text)
    has_one = bool(re.search(r"[(（]1[)）]", compact))
    has_later = bool(re.search(r"[(（][2-9][)）]", compact))
    return has_one and not has_later


def _looks_unfinished(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    return stripped.endswith(("；", ";", "：", ":", "，", ",", "、"))


def _looks_like_next_page_continuation(text: str | None) -> bool:
    compact = _compact(text)
    if not compact:
        return False
    continuation_patterns = [
        r"^[(（]2[)）]",
        r"^解析",
        r"^答案",
        r"[(（]2[)）]证明",
        r"[(（]2[)）]求证",
    ]
    return any(re.search(pattern, compact) for pattern in continuation_patterns)


@dataclass
class Candidate:
    question_id: str
    quality_label: str
    difficulty: str
    source_name: str
    page_no: int | None
    question_text: str
    answer: str
    solution: str
    next_page_text: str
    score: int
    reasons: list[str]


def score_candidate(row: dict[str, Any]) -> Candidate | None:
    question_text = row["question_text"] or ""
    answer = row["answer"] or ""
    solution = row["solution"] or ""
    next_page_text = row["next_page_text"] or ""
    reasons: list[str] = []
    score = 0

    if not answer.strip():
        score += 2
        reasons.append("answer 为空")
    if not solution.strip():
        score += 2
        reasons.append("solution 为空")
    if _has_part_one_only(question_text):
        score += 2
        reasons.append("只抽到 (1)，未抽到后续小问")
    if _looks_unfinished(question_text):
        score += 1
        reasons.append("题干以未完成标点结尾")
    if _looks_like_next_page_continuation(next_page_text):
        score += 4
        reasons.append("下一页疑似从 (2)/解析/答案 继续")
    if len(_compact(question_text)) < 80:
        score += 1
        reasons.append("题干偏短")

    if score < 5:
        return None

    return Candidate(
        question_id=row["id"],
        quality_label=row["quality_label"] or "",
        difficulty=row["difficulty"] or "",
        source_name=row["source_name"] or "",
        page_no=row["page_no"],
        question_text=question_text,
        answer=answer,
        solution=solution,
        next_page_text=next_page_text,
        score=score,
        reasons=reasons,
    )


def fetch_candidate_rows(cur) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT
          qi.id::text,
          COALESCE(qi.quality_label, '') AS quality_label,
          COALESCE(qi.difficulty, '') AS difficulty,
          qi.question_text,
          COALESCE(qi.answer, '') AS answer,
          COALESCE(qi.solution, '') AS solution,
          qi.metadata AS question_metadata,
          COALESCE(d.source_name, '') AS source_name,
          qi.document_id::text,
          COALESCE(tb.metadata, '{}'::jsonb) AS block_metadata
        FROM question_items qi
        LEFT JOIN documents d ON d.id = qi.document_id
        LEFT JOIN text_blocks tb ON tb.id = qi.text_block_id
        WHERE COALESCE(qi.quality_label, '') IN ('medium', 'pending_review')
          AND (
            COALESCE(qi.answer, '') = ''
            OR COALESCE(qi.solution, '') = ''
          )
          AND COALESCE(qi.metadata->>'review_status', '') <> %s
        ORDER BY d.source_name, qi.metadata->>'page_no', qi.created_at
        """,
        (INCOMPLETE_STATUS,),
    )
    rows: list[dict[str, Any]] = []
    for raw in cur.fetchall():
        q_meta = _json_dict(raw[6])
        block_meta = _json_dict(raw[9])
        page_no = _page_no(q_meta, block_meta.get("page_no"))
        next_page_text = ""
        if raw[8] and page_no is not None:
            cur.execute(
                """
                SELECT COALESCE(llm_rewritten_text, cleaned_text, raw_text, '')
                FROM text_blocks
                WHERE document_id = %s
                  AND metadata->>'page_no' = %s
                ORDER BY block_index
                LIMIT 1
                """,
                (raw[8], str(page_no + 1)),
            )
            next_row = cur.fetchone()
            next_page_text = next_row[0] if next_row else ""
        rows.append(
            {
                "id": raw[0],
                "quality_label": raw[1],
                "difficulty": raw[2],
                "question_text": raw[3],
                "answer": raw[4],
                "solution": raw[5],
                "source_name": raw[7],
                "document_id": raw[8],
                "page_no": page_no,
                "next_page_text": next_page_text,
            }
        )
    return rows


def repair_candidates(cur, candidates: list[Candidate]) -> None:
    for item in candidates:
        review_payload = {
            "review_status": INCOMPLETE_STATUS,
            "review_note": "疑似跨页例题被误抽为单独题目，答案/解析在下一页或后续页，已排除推荐与正式检索。",
            "exclude_from_recommendation": True,
            "repair_reason": item.reasons,
            "repair_score": item.score,
        }
        cur.execute(
            """
            UPDATE question_items
            SET quality_label = 'low',
                metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(review_payload, ensure_ascii=False), item.question_id),
        )


def write_report(candidates: list[Candidate], *, apply: bool) -> None:
    lines = [
        "# Cross-page Incomplete Question Repair Report",
        "",
        f"- Mode: {'apply' if apply else 'dry-run'}",
        f"- Candidate count: {len(candidates)}",
        "",
        "## Repair Rule",
        "",
        "- Scope: `question_items.quality_label IN ('medium', 'pending_review')`",
        "- Trigger: answer 或 solution 为空，并且题干/下一页符合跨页残缺特征。",
        "- Apply action: 将题目标记为 `low`，写入 `metadata.review_status=bad_split_cross_page`，从推荐与正式检索中排除。",
        "",
        "## Candidates",
        "",
    ]
    if not candidates:
        lines.append("- None")
    for item in candidates:
        lines.extend(
            [
                f"### {item.question_id}",
                "",
                f"- Source: `{item.source_name}`",
                f"- Page: {item.page_no}",
                f"- Quality: {item.quality_label}",
                f"- Score: {item.score}",
                f"- Reasons: {'; '.join(item.reasons)}",
                f"- Question: `{_preview(item.question_text)}`",
                f"- Answer: `{_preview(item.answer, 80)}`",
                f"- Solution: `{_preview(item.solution, 100)}`",
                f"- Next page preview: `{_preview(item.next_page_text)}`",
                "",
            ]
        )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan and repair suspected cross-page incomplete question_items."
    )
    parser.add_argument("--apply", action="store_true", help="Apply repair updates to PostgreSQL.")
    parser.add_argument("--limit", type=int, default=0, help="Limit candidate count after scoring.")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    with connect_pg() as conn:
        with conn.cursor() as cur:
            rows = fetch_candidate_rows(cur)
            candidates = [candidate for row in rows if (candidate := score_candidate(row))]
            candidates.sort(key=lambda item: (-item.score, item.source_name, item.page_no or 0))
            if args.limit > 0:
                candidates = candidates[: args.limit]
            if args.apply:
                repair_candidates(cur, candidates)
                conn.commit()
        write_report(candidates, apply=args.apply)

    print(f"candidates={len(candidates)}")
    print(f"report={REPORT_PATH}")
    if args.apply:
        print("repair=applied")
    else:
        print("repair=dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
