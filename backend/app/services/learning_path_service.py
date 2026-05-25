from datetime import datetime, timezone

from app.core.config import settings
from app.prompts.learning_path_prompt import build_learning_path_messages
from app.repositories.knowledge_repository import load_knowledge_points
from app.schemas.learning_path import (
    LearningPath,
    LearningPathMilestone,
    LearningPathTask,
)
from app.services.llm_service import is_enabled_flag, is_llm_enabled, safe_generate_text
from app.services.profile_service import get_student_profile, get_wrong_records


def _parse_llm_json(content: str | None) -> dict | None:
    import json
    import re

    if not content:
        return None
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _build_prerequisite_map() -> dict[str, list[str]]:
    points = load_knowledge_points()
    return {p.name: p.prerequisites for p in points if p.prerequisites}


def _sort_by_prerequisites(
    weak_names: list[str], prereq_map: dict[str, list[str]]
) -> list[str]:
    resolved = []
    visited = set()

    def visit(name: str):
        if name in visited:
            return
        visited.add(name)
        for dep in prereq_map.get(name, []):
            if dep in weak_names:
                visit(dep)
        if name not in resolved:
            resolved.append(name)

    for name in weak_names:
        visit(name)
    return resolved


TASK_TEMPLATES = {
    "复习": "回顾“{point}”的核心结论和标准步骤，整理成笔记。",
    "练习": "完成 2-3 道“{point}”的基础题，核对步骤完整性。",
    "测试": "限时 15 分钟完成 1 道“{point}”的中等题，检验掌握程度。",
}


def _rule_learning_path(
    student_id: str,
    profile: dict,
    records: list[dict],
) -> LearningPath:
    weak_points = profile.get("weak_points", {}) or {}
    error_types = profile.get("error_types", {}) or {}
    prereq_map = _build_prerequisite_map()

    sorted_weak = sorted(weak_points.items(), key=lambda x: x[1], reverse=True)
    weak_names = [name for name, _ in sorted_weak[:6]]

    priority_order = _sort_by_prerequisites(weak_names, prereq_map)
    if not priority_order:
        priority_order = ["函数单调性", "导数计算", "导数与函数单调性"]

    daily_tasks = []
    day = 1
    for i, point in enumerate(priority_order):
        if i > 0 and i % 2 == 0:
            day += 1
        task_type = "复习" if i < 2 else "练习"
        daily_tasks.append(
            LearningPathTask(
                day=day,
                knowledge_point=point,
                task_type=task_type,
                description=TASK_TEMPLATES[task_type].format(point=point),
            )
        )
        if i < len(priority_order) - 1 and i % 2 == 1:
            daily_tasks.append(
                LearningPathTask(
                    day=day,
                    knowledge_point=point,
                    task_type="测试",
                    description=TASK_TEMPLATES["测试"].format(point=point),
                )
            )
            day += 1

    if not daily_tasks:
        daily_tasks = [
            LearningPathTask(
                day=1,
                knowledge_point="函数与导数",
                task_type="练习",
                description="完成 3 道函数与导数综合基础题。",
            )
        ]

    milestones = []
    if len(priority_order) >= 2:
        milestones.append(
            LearningPathMilestone(
                day=3,
                description=f"完成“{priority_order[0]}”和“{priority_order[1]}”的复习与练习。",
                checkpoints=[
                    f"能独立完成{priority_order[0]}的基础题",
                    f"能独立完成{priority_order[1]}的基础题",
                ],
            )
        )
    if len(priority_order) >= 4:
        milestones.append(
            LearningPathMilestone(
                day=6,
                description="完成所有薄弱知识点的第一轮复习。",
                checkpoints=[
                    "各知识点错题复盘完成",
                    "能正确写出解题步骤",
                ],
            )
        )

    estimated_days = max(day, len(priority_order) + 1)

    return LearningPath(
        student_id=student_id,
        priority_order=priority_order,
        daily_tasks=daily_tasks,
        milestones=milestones,
        estimated_days=min(estimated_days, 14),
        generated_at=datetime.now(timezone.utc).isoformat(),
        source="rule",
    )


def generate_learning_path(student_id: str) -> LearningPath:
    profile_data = get_student_profile(student_id)
    profile = profile_data.model_dump() if hasattr(profile_data, "model_dump") else {}
    records = get_wrong_records(student_id, limit=20)

    rule_path = _rule_learning_path(student_id, profile, records)

    if not is_enabled_flag(settings.enable_llm_learning_path) or not is_llm_enabled():
        return rule_path

    prereq_map = _build_prerequisite_map()
    weak_points_raw = profile.get("weak_points", []) or []
    if isinstance(weak_points_raw, list):
        weak_points = [
            {"name": p.name, "count": p.count}
            for p in weak_points_raw
            if hasattr(p, "name")
        ] or [{"name": p["name"], "count": p["count"]} for p in weak_points_raw if isinstance(p, dict)]
    else:
        weak_points = []

    error_types = profile.get("error_types", {}) or {}
    if hasattr(error_types, "items"):
        error_types_dict = dict(error_types)
    else:
        error_types_dict = {}

    recent_records = [
        {
            "question_text": r.get("question_text", "") if isinstance(r, dict) else getattr(r, "question_text", ""),
            "error_type": r.get("error_type", "") if isinstance(r, dict) else getattr(r, "error_type", ""),
        }
        for r in (records[:5] if isinstance(records, list) else [])
    ]

    messages = build_learning_path_messages(
        student_id=student_id,
        grade=profile.get("grade", "高三"),
        target_score=profile.get("target_score"),
        current_score=profile.get("current_score"),
        weak_points=weak_points,
        error_types=error_types_dict,
        recent_records=recent_records,
        prerequisite_map=prereq_map,
    )

    content = safe_generate_text(
        messages=messages,
        max_tokens=1500,
        temperature=0.2,
        fallback=None,
    )
    data = _parse_llm_json(content)
    if not data:
        return rule_path

    try:
        priority_order = data.get("priority_order", rule_path.priority_order)
        daily_tasks_raw = data.get("daily_tasks", [])
        milestones_raw = data.get("milestones", [])

        daily_tasks = [
            LearningPathTask(
                day=t.get("day", 1),
                knowledge_point=t.get("knowledge_point", ""),
                task_type=t.get("task_type", "练习"),
                description=t.get("description", ""),
            )
            for t in daily_tasks_raw
            if isinstance(t, dict)
        ]
        milestones = [
            LearningPathMilestone(
                day=m.get("day", 3),
                description=m.get("description", ""),
                checkpoints=m.get("checkpoints", []),
            )
            for m in milestones_raw
            if isinstance(m, dict)
        ]

        if not daily_tasks:
            return rule_path

        return LearningPath(
            student_id=student_id,
            priority_order=priority_order,
            daily_tasks=daily_tasks,
            milestones=milestones,
            estimated_days=data.get("estimated_days", rule_path.estimated_days),
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="llm",
        )
    except (KeyError, TypeError, ValueError):
        return rule_path
