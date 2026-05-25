import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import STORAGE_DIR


PRACTICE_ATTEMPTS_PATH = STORAGE_DIR / "practice_attempts.json"
PRACTICE_EVENTS_PATH = STORAGE_DIR / "practice_events.json"


def _connect_pg():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        connect_timeout=2,
    )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _ensure_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS student_practice_attempts (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL,
            student_input TEXT,
            ocr_image_path TEXT,
            recognized_answer TEXT,
            score INTEGER,
            is_correct BOOLEAN,
            feedback TEXT,
            assist_mode TEXT NOT NULL DEFAULT 'grade',
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS student_practice_events (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            question_id TEXT NOT NULL,
            attempt_id TEXT REFERENCES student_practice_attempts(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_student_practice_attempts_student_id "
        "ON student_practice_attempts(student_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_student_practice_events_student_id "
        "ON student_practice_events(student_id)"
    )


def _ensure_student(cur, student_id: str) -> None:
    cur.execute(
        """
        INSERT INTO students (id)
        VALUES (%s)
        ON CONFLICT (id) DO NOTHING
        """,
        (student_id,),
    )


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_practice_attempt(attempt: dict[str, Any]) -> None:
    if _pg_save_attempt(attempt):
        return

    attempts = _read_json(PRACTICE_ATTEMPTS_PATH, [])
    attempts.append({**attempt, "created_at": _now_text(), "updated_at": _now_text()})
    _write_json(PRACTICE_ATTEMPTS_PATH, attempts)


def add_practice_event(event: dict[str, Any]) -> None:
    if _pg_add_event(event):
        return

    events = _read_json(PRACTICE_EVENTS_PATH, [])
    events.append({**event, "created_at": _now_text()})
    _write_json(PRACTICE_EVENTS_PATH, events)


def _pg_save_attempt(attempt: dict[str, Any]) -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                _ensure_tables(cur)
                _ensure_student(cur, attempt["student_id"])
                cur.execute(
                    """
                    INSERT INTO student_practice_attempts (
                        id, student_id, question_id, student_input,
                        ocr_image_path, recognized_answer, score,
                        is_correct, feedback, assist_mode, metadata,
                        created_at, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, now(), now()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        student_input = EXCLUDED.student_input,
                        ocr_image_path = EXCLUDED.ocr_image_path,
                        recognized_answer = EXCLUDED.recognized_answer,
                        score = EXCLUDED.score,
                        is_correct = EXCLUDED.is_correct,
                        feedback = EXCLUDED.feedback,
                        assist_mode = EXCLUDED.assist_mode,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                    """,
                    (
                        attempt["id"],
                        attempt["student_id"],
                        attempt["question_id"],
                        attempt.get("student_input"),
                        attempt.get("ocr_image_path"),
                        attempt.get("recognized_answer"),
                        attempt.get("score"),
                        attempt.get("is_correct"),
                        attempt.get("feedback"),
                        attempt.get("assist_mode", "grade"),
                        json.dumps(attempt.get("metadata", {}), ensure_ascii=False),
                    ),
                )
        return True
    except Exception:
        return False


def _pg_add_event(event: dict[str, Any]) -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                _ensure_tables(cur)
                _ensure_student(cur, event["student_id"])
                cur.execute(
                    """
                    INSERT INTO student_practice_events (
                        id, student_id, question_id, attempt_id,
                        event_type, event_payload, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        event["id"],
                        event["student_id"],
                        event["question_id"],
                        event.get("attempt_id"),
                        event["event_type"],
                        json.dumps(event.get("event_payload", {}), ensure_ascii=False),
                    ),
                )
        return True
    except Exception:
        return False
