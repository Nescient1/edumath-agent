import json
import re
from typing import Any

from app.core.config import settings
from app.db.models import new_record_id
from app.repositories.profile_repository import (
    add_wrong_record,
    get_profile,
    list_wrong_records,
    now_text,
    save_profile,
    update_profile_fields,
    update_wrong_record,
)
from app.schemas.profile import (
    ProfileAdvice,
    ProfileAdviceItem,
    ProfileWeeklyTask,
    StudentProfile,
    StudentProfileUpdate,
    WeakPoint,
    WrongQuestionRecord,
    WrongQuestionRecordUpdate,
)
from app.services.llm_service import is_enabled_flag, is_llm_enabled, safe_generate_text


def _build_recommendation(weak_points: dict[str, int]) -> str:
    if not weak_points:
        return "当前还没有错题记录，建议先完成一次错题诊断。"

    top_point = max(weak_points.items(), key=lambda item: item[1])[0]
    return f"建议优先复习“{top_point}”，先回看核心结论，再完成 3 道同类基础题。"


def _weak_points_to_dict(points: list[WeakPoint] | None) -> dict[str, int] | None:
    if points is None:
        return None
    return {item.name: item.count for item in points if item.name.strip()}


def _top_items(source: dict[str, int], limit: int = 4) -> list[str]:
    return [
        name
        for name, _count in sorted(source.items(), key=lambda item: item[1], reverse=True)[
            :limit
        ]
        if name
    ]


def _rule_based_profile_advice(profile: dict[str, Any], records: list[dict]) -> ProfileAdvice:
    weak_points = profile.get("weak_points", {}) or {}
    error_types = profile.get("error_types", {}) or {}
    priority_points = _top_items(weak_points) or ["函数与导数基础", "导数与单调性"]
    top_error_types = _top_items(error_types, limit=3)

    mistake_advice = [
        ProfileAdviceItem(
            title="先补最集中的知识点",
            action=f"优先复习 {priority_points[0]}，把定义、公式、标准步骤各整理成一张小卡片。",
        ),
        ProfileAdviceItem(
            title="错题复盘要写清原因",
            action="每道错题至少标出“卡在哪里、少了哪一步、下次先检查什么”。",
        ),
    ]
    if top_error_types:
        mistake_advice.append(
            ProfileAdviceItem(
                title="针对主要错因做训练",
                action=f"近期错因集中在“{top_error_types[0]}”，建议连续做 3 道同类题并核对步骤完整性。",
            )
        )

    return ProfileAdvice(
        summary=(
            "当前画像建议先做小范围、可检查的复习：抓住最高频薄弱点，"
            "用少量同类题确认方法是否真正掌握。"
        ),
        priority_points=priority_points,
        mistake_advice=mistake_advice,
        weekly_plan=[
            ProfileWeeklyTask(day="第 1 天", task=f"复习 {priority_points[0]} 的概念和标准步骤。"),
            ProfileWeeklyTask(day="第 2 天", task="完成 3 道基础同类题，重点检查定义域和符号判断。"),
            ProfileWeeklyTask(day="第 3 天", task="复盘最近错题，把易错步骤写成检查清单。"),
            ProfileWeeklyTask(day="第 4-7 天", task="隔天重做错题，并补 2 道中等难度迁移题。"),
        ],
        generated_at=now_text(),
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_profile_advice(data: Any) -> ProfileAdvice | None:
    if isinstance(data, ProfileAdvice):
        return data
    if not isinstance(data, dict):
        return None

    try:
        return ProfileAdvice(
            summary=str(data.get("summary", "")),
            priority_points=[
                str(item) for item in data.get("priority_points", []) if str(item).strip()
            ],
            mistake_advice=[
                ProfileAdviceItem(
                    title=str(item.get("title", "")),
                    action=str(item.get("action", "")),
                )
                for item in data.get("mistake_advice", [])
                if isinstance(item, dict)
            ],
            weekly_plan=[
                ProfileWeeklyTask(
                    day=str(item.get("day", "")),
                    task=str(item.get("task", "")),
                )
                for item in data.get("weekly_plan", [])
                if isinstance(item, dict)
            ],
            generated_at=str(data.get("generated_at") or now_text()),
        )
    except Exception:
        return None


def _cached_profile_advice(profile: dict[str, Any]) -> ProfileAdvice | None:
    metadata = profile.get("metadata") or {}
    advice = metadata.get("advice")
    return _normalize_profile_advice(advice)


def _save_profile_advice(profile: dict[str, Any], advice: ProfileAdvice) -> None:
    metadata = profile.setdefault("metadata", {})
    metadata["advice"] = advice.model_dump()
    profile["updated_at"] = now_text()
    save_profile(profile)


def generate_profile_advice(profile: dict[str, Any], records: list[dict]) -> ProfileAdvice:
    fallback_advice = _rule_based_profile_advice(profile, records)
    if not is_enabled_flag(settings.enable_llm_profile_advice) or not is_llm_enabled():
        return fallback_advice

    recent_records = [
        {
            "knowledge_points": item.get("knowledge_points", []),
            "error_type": item.get("error_type", ""),
            "diagnosis": item.get("diagnosis", "")[:180],
            "created_at": item.get("created_at", ""),
        }
        for item in records[:8]
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "你是高中数学学习规划助手。请只输出 JSON，不要输出 Markdown。"
                "JSON 字段必须包含 summary, priority_points, mistake_advice, weekly_plan。"
                "mistake_advice 每项包含 title 和 action，weekly_plan 每项包含 day 和 task。"
                "建议要面向高中生，短句、可执行，不要编造不存在的记录。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "grade": profile.get("grade"),
                    "target_score": profile.get("target_score"),
                    "current_score": profile.get("current_score"),
                    "weak_points": profile.get("weak_points", {}),
                    "error_types": profile.get("error_types", {}),
                    "total_wrong_questions": profile.get("total_wrong_questions", 0),
                    "recent_wrong_records": recent_records,
                },
                ensure_ascii=False,
            ),
        },
    ]
    generated = safe_generate_text(
        messages=messages,
        max_tokens=900,
        temperature=0.2,
        fallback=None,
    )
    if not generated:
        return fallback_advice

    parsed = _extract_json_object(generated)
    return _normalize_profile_advice(parsed) or fallback_advice


def refresh_student_profile_advice(student_id: str) -> ProfileAdvice:
    profile = get_profile(student_id)
    records = list_wrong_records(student_id, limit=30)
    advice = generate_profile_advice(profile, records)
    _save_profile_advice(profile, advice)
    return advice


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
    for point in knowledge_points:
        mastery = profile.setdefault("mastery", {})
        current = mastery.get(point, 0)
        if isinstance(current, (int, float)):
            mastery[point] = max(0, int(current) - 1)
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
            "review_status": "未复习",
            "is_mastered": False,
            "created_at": now_text(),
        }
    )
    return record_id


def get_student_profile(student_id: str) -> StudentProfile:
    profile = get_profile(student_id)
    weak_points = profile.get("weak_points", {})
    ranked_points = sorted(weak_points.items(), key=lambda item: item[1], reverse=True)
    recommendation = _build_recommendation(weak_points)
    advice = _cached_profile_advice(profile)

    return StudentProfile(
        student_id=student_id,
        name=profile.get("name", ""),
        grade=profile.get("grade", "高三"),
        target_score=profile.get("target_score", 120),
        current_score=profile.get("current_score"),
        textbook_version=profile.get("textbook_version", ""),
        current_topic=profile.get("current_topic", "函数与导数"),
        learning_goal=profile.get("learning_goal", ""),
        weak_points=[WeakPoint(name=name, count=count) for name, count in ranked_points],
        error_types=profile.get("error_types", {}),
        mastery=profile.get("mastery", {}),
        total_wrong_questions=profile.get("total_wrong_questions", 0),
        recommendation=recommendation,
        llm_advice=advice.summary if advice else None,
        advice=advice,
        updated_at=profile.get("updated_at"),
    )


def get_wrong_records(
    student_id: str,
    limit: int = 20,
    offset: int = 0,
) -> list[WrongQuestionRecord]:
    return [
        WrongQuestionRecord(**item)
        for item in list_wrong_records(student_id, limit=limit, offset=offset)
    ]


def edit_student_profile(
    student_id: str,
    req: StudentProfileUpdate,
) -> StudentProfile:
    updates = req.model_dump(exclude_unset=True)
    if "weak_points" in updates:
        updates["weak_points"] = _weak_points_to_dict(req.weak_points)
    update_profile_fields(student_id, updates)
    return get_student_profile(student_id)


def edit_wrong_record(
    student_id: str,
    record_id: str,
    req: WrongQuestionRecordUpdate,
) -> WrongQuestionRecord | None:
    updates = req.model_dump(exclude_unset=True)
    record = update_wrong_record(student_id, record_id, updates)
    if not record:
        return None

    if req.is_mastered is not None:
        profile = get_profile(student_id)
        mastery = profile.setdefault("mastery", {})
        for point in record.get("knowledge_points", []):
            mastery[point] = 100 if req.is_mastered else min(60, int(mastery.get(point, 0) or 0))
        profile["updated_at"] = now_text()
        save_profile(profile)

    return WrongQuestionRecord(**record)
