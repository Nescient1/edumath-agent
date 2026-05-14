import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import STORAGE_DIR


PROFILES_PATH = STORAGE_DIR / "profiles.json"
WRONG_RECORDS_PATH = STORAGE_DIR / "wrong_records.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_profile(student_id: str) -> dict[str, Any]:
    profiles = _read_json(PROFILES_PATH, {})
    profile = profiles.get(student_id)
    if profile:
        return profile

    return {
        "student_id": student_id,
        "grade": "高三",
        "target_score": 120,
        "weak_points": {},
        "error_types": {},
        "total_wrong_questions": 0,
        "updated_at": None,
    }


def save_profile(profile: dict[str, Any]) -> None:
    profiles = _read_json(PROFILES_PATH, {})
    profiles[profile["student_id"]] = profile
    _write_json(PROFILES_PATH, profiles)


def add_wrong_record(record: dict[str, Any]) -> None:
    records = _read_json(WRONG_RECORDS_PATH, [])
    records.append(record)
    _write_json(WRONG_RECORDS_PATH, records)


def list_wrong_records(student_id: str) -> list[dict[str, Any]]:
    records = _read_json(WRONG_RECORDS_PATH, [])
    filtered = [item for item in records if item["student_id"] == student_id]
    return sorted(filtered, key=lambda item: item["created_at"], reverse=True)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
