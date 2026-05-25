import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import STORAGE_DIR


PROFILES_PATH = STORAGE_DIR / "profiles.json"
WRONG_RECORDS_PATH = STORAGE_DIR / "wrong_records.json"


DEFAULT_PROFILE = {
    "grade": "高三",
    "target_score": 120,
    "current_score": None,
    "textbook_version": "",
    "current_topic": "函数与导数",
    "learning_goal": "",
    "weak_points": {},
    "error_types": {},
    "mastery": {},
    "total_wrong_questions": 0,
    "metadata": {},
    "updated_at": None,
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json_default_profile(student_id: str) -> dict[str, Any]:
    return {"student_id": student_id, **deepcopy(DEFAULT_PROFILE)}


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


def _pg_available() -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def _as_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _ensure_pg_student(cur, student_id: str) -> None:
    cur.execute(
        """
        INSERT INTO students (id)
        VALUES (%s)
        ON CONFLICT (id) DO NOTHING
        """,
        (student_id,),
    )
    cur.execute(
        """
        INSERT INTO student_profiles (student_id)
        VALUES (%s)
        ON CONFLICT (student_id) DO NOTHING
        """,
        (student_id,),
    )


def _pg_get_profile(student_id: str) -> dict[str, Any] | None:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                _ensure_pg_student(cur, student_id)
                cur.execute(
                    """
                    SELECT
                      s.id, s.name, s.grade, s.target_score, s.current_score,
                      COALESCE(s.textbook_version, ''),
                      COALESCE(s.current_topic, ''),
                      COALESCE(s.learning_goal, ''),
                      p.weak_points, p.error_types, p.mastery,
                      p.total_wrong_questions,
                      p.metadata,
                      to_char(p.updated_at, 'YYYY-MM-DD HH24:MI:SS')
                    FROM students s
                    JOIN student_profiles p ON p.student_id = s.id
                    WHERE s.id = %s
                    """,
                    (student_id,),
                )
                row = cur.fetchone()
                conn.commit()
    except Exception:
        return None

    if not row:
        return None
    return {
        "student_id": row[0],
        "name": row[1] or "",
        "grade": row[2] or "高三",
        "target_score": row[3] or 120,
        "current_score": row[4],
        "textbook_version": row[5] or "",
        "current_topic": row[6] or "函数与导数",
        "learning_goal": row[7] or "",
        "weak_points": _as_json(row[8]) or {},
        "error_types": _as_json(row[9]) or {},
        "mastery": _as_json(row[10]) or {},
        "total_wrong_questions": row[11] or 0,
        "metadata": _as_json(row[12]) or {},
        "updated_at": row[13],
    }


def _pg_save_profile(profile: dict[str, Any]) -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                student_id = profile["student_id"]
                _ensure_pg_student(cur, student_id)
                cur.execute(
                    """
                    UPDATE students
                    SET name = COALESCE(%s, name),
                        grade = COALESCE(%s, grade),
                        target_score = COALESCE(%s, target_score),
                        current_score = %s,
                        textbook_version = %s,
                        current_topic = %s,
                        learning_goal = %s,
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        profile.get("name"),
                        profile.get("grade"),
                        profile.get("target_score"),
                        profile.get("current_score"),
                        profile.get("textbook_version") or "",
                        profile.get("current_topic") or "",
                        profile.get("learning_goal") or "",
                        student_id,
                    ),
                )
                cur.execute(
                    """
                    UPDATE student_profiles
                    SET weak_points = %s::jsonb,
                        error_types = %s::jsonb,
                        mastery = %s::jsonb,
                        total_wrong_questions = %s,
                        metadata = %s::jsonb,
                        updated_at = now()
                    WHERE student_id = %s
                    """,
                    (
                        json.dumps(profile.get("weak_points", {}), ensure_ascii=False),
                        json.dumps(profile.get("error_types", {}), ensure_ascii=False),
                        json.dumps(profile.get("mastery", {}), ensure_ascii=False),
                        profile.get("total_wrong_questions", 0),
                        json.dumps(profile.get("metadata", {}), ensure_ascii=False),
                        student_id,
                    ),
                )
        return True
    except Exception:
        return False


def get_profile(student_id: str) -> dict[str, Any]:
    pg_profile = _pg_get_profile(student_id)
    if pg_profile:
        return pg_profile

    profiles = _read_json(PROFILES_PATH, {})
    profile = profiles.get(student_id)
    if profile:
        return {**_json_default_profile(student_id), **profile}

    return _json_default_profile(student_id)


def save_profile(profile: dict[str, Any]) -> None:
    profile["updated_at"] = now_text()
    if _pg_save_profile(profile):
        return

    profiles = _read_json(PROFILES_PATH, {})
    profiles[profile["student_id"]] = profile
    _write_json(PROFILES_PATH, profiles)


def update_profile_fields(student_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    profile = get_profile(student_id)
    editable_fields = {
        "name",
        "grade",
        "target_score",
        "current_score",
        "textbook_version",
        "current_topic",
        "learning_goal",
        "weak_points",
        "error_types",
        "mastery",
        "metadata",
    }
    for key, value in updates.items():
        if key in editable_fields and value is not None:
            profile[key] = value
    save_profile(profile)
    return get_profile(student_id)


def add_wrong_record(record: dict[str, Any]) -> None:
    if _pg_add_wrong_record(record):
        return

    records = _read_json(WRONG_RECORDS_PATH, [])
    records.append(record)
    _write_json(WRONG_RECORDS_PATH, records)


def _pg_add_wrong_record(record: dict[str, Any]) -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                _ensure_pg_student(cur, record["student_id"])
                cur.execute(
                    """
                    INSERT INTO student_wrong_records (
                        id, student_id, question_text, student_answer,
                        knowledge_points, error_type, diagnosis,
                        review_status, is_mastered, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        record["id"],
                        record["student_id"],
                        record["question_text"],
                        record.get("student_answer"),
                        json.dumps(record.get("knowledge_points", []), ensure_ascii=False),
                        record["error_type"],
                        record["diagnosis"],
                        record.get("review_status", "未复习"),
                        bool(record.get("is_mastered", False)),
                    ),
                )
        return True
    except Exception:
        return False


def list_wrong_records(
    student_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    pg_records = _pg_list_wrong_records(student_id, limit=limit, offset=offset)
    if pg_records is not None:
        return pg_records

    records = _read_json(WRONG_RECORDS_PATH, [])
    filtered = [item for item in records if item["student_id"] == student_id]
    sorted_records = sorted(filtered, key=lambda item: item["created_at"], reverse=True)
    return sorted_records[offset : offset + limit]


def _pg_list_wrong_records(
    student_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]] | None:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, student_id, question_text, student_answer,
                           knowledge_points, error_type, diagnosis,
                           review_status, is_mastered,
                           to_char(created_at, 'YYYY-MM-DD HH24:MI:SS'),
                           to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS')
                    FROM student_wrong_records
                    WHERE student_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (student_id, limit, offset),
                )
                rows = cur.fetchall()
    except Exception:
        return None

    return [
        {
            "id": row[0],
            "student_id": row[1],
            "question_text": row[2],
            "student_answer": row[3],
            "knowledge_points": _as_json(row[4]) or [],
            "error_type": row[5],
            "diagnosis": row[6],
            "review_status": row[7],
            "is_mastered": row[8],
            "created_at": row[9],
            "updated_at": row[10],
        }
        for row in rows
    ]


def update_wrong_record(
    student_id: str,
    record_id: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    if _pg_update_wrong_record(student_id, record_id, updates):
        return next(
            (item for item in list_wrong_records(student_id) if item["id"] == record_id),
            None,
        )

    records = _read_json(WRONG_RECORDS_PATH, [])
    updated_record = None
    for item in records:
        if item["id"] == record_id and item["student_id"] == student_id:
            if "review_status" in updates and updates["review_status"] is not None:
                item["review_status"] = updates["review_status"]
            if "is_mastered" in updates and updates["is_mastered"] is not None:
                item["is_mastered"] = updates["is_mastered"]
            item["updated_at"] = now_text()
            updated_record = item
            break
    if updated_record:
        _write_json(WRONG_RECORDS_PATH, records)
    return updated_record


def _pg_update_wrong_record(
    student_id: str,
    record_id: str,
    updates: dict[str, Any],
) -> bool:
    try:
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE student_wrong_records
                    SET review_status = COALESCE(%s, review_status),
                        is_mastered = COALESCE(%s, is_mastered),
                        updated_at = now()
                    WHERE id = %s AND student_id = %s
                    """,
                    (
                        updates.get("review_status"),
                        updates.get("is_mastered"),
                        record_id,
                        student_id,
                    ),
                )
                return cur.rowcount > 0
    except Exception:
        return False


def migrate_json_profiles_to_postgres() -> dict[str, int | bool]:
    if not _pg_available():
        return {"db_available": False, "profiles": 0, "records": 0}

    profiles = _read_json(PROFILES_PATH, {})
    records = _read_json(WRONG_RECORDS_PATH, [])
    profile_count = 0
    record_count = 0
    for student_id, profile in profiles.items():
        save_profile({**_json_default_profile(student_id), **profile})
        profile_count += 1
    for record in records:
        if _pg_add_wrong_record(record):
            record_count += 1
    return {"db_available": True, "profiles": profile_count, "records": record_count}
