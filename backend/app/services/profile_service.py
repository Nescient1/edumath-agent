from app.db.models import new_record_id
from app.repositories.profile_repository import (
    add_wrong_record,
    get_profile,
    list_wrong_records,
    now_text,
    save_profile,
)
from app.schemas.profile import StudentProfile, WeakPoint, WrongQuestionRecord


def _build_recommendation(weak_points: dict[str, int]) -> str:
    if not weak_points:
        return "当前还没有错题记录，建议先完成一次错题诊断。"

    top_point = max(weak_points.items(), key=lambda item: item[1])[0]
    return f"建议优先复习“{top_point}”，先回看核心结论，再完成 3 道同类基础题。"


def update_student_profile(
    student_id: str,
    knowledge_points: list[str],
    error_type: str,
) -> None:
    profile = get_profile(student_id)
    weak_points = profile.setdefault("weak_points", {})
    error_types = profile.setdefault("error_types", {})

    for point in knowledge_points:
        weak_points[point] = weak_points.get(point, 0) + 1

    error_types[error_type] = error_types.get(error_type, 0) + 1
    profile["total_wrong_questions"] = profile.get("total_wrong_questions", 0) + 1
    profile["updated_at"] = now_text()
    save_profile(profile)


def save_wrong_question_record(
    student_id: str,
    question_text: str,
    student_answer: str | None,
    knowledge_points: list[str],
    error_type: str,
    diagnosis: str,
) -> str:
    record_id = new_record_id("W")
    add_wrong_record(
        {
            "id": record_id,
            "student_id": student_id,
            "question_text": question_text,
            "student_answer": student_answer,
            "knowledge_points": knowledge_points,
            "error_type": error_type,
            "diagnosis": diagnosis,
            "created_at": now_text(),
        }
    )
    return record_id


def get_student_profile(student_id: str) -> StudentProfile:
    profile = get_profile(student_id)
    weak_points = profile.get("weak_points", {})
    ranked_points = sorted(weak_points.items(), key=lambda item: item[1], reverse=True)

    return StudentProfile(
        student_id=student_id,
        grade=profile.get("grade", "高三"),
        target_score=profile.get("target_score", 120),
        weak_points=[WeakPoint(name=name, count=count) for name, count in ranked_points],
        error_types=profile.get("error_types", {}),
        total_wrong_questions=profile.get("total_wrong_questions", 0),
        recommendation=_build_recommendation(weak_points),
        updated_at=profile.get("updated_at"),
    )


def get_wrong_records(student_id: str) -> list[WrongQuestionRecord]:
    return [WrongQuestionRecord(**item) for item in list_wrong_records(student_id)]
