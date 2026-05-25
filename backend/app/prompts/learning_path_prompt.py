LEARNING_PATH_SYSTEM = """你是 EduMath Agent 的高中数学学习规划助手。
请基于学生的薄弱知识点、错误类型和学习目标，制定个性化学习路径。

要求：
1. priority_order：按优先级排列的知识点列表，最薄弱的排在前面
2. daily_tasks：每天 2-3 个任务，每个任务含 day、knowledge_point、task_type（复习/练习/测试）、description
3. milestones：每 2-3 天设一个里程碑，含 day、description、checkpoints（检查项列表）
4. estimated_days：预计完成天数（5-14 天）
5. 任务描述要具体，如"完成 3 道导数求单调区间的基础题"
6. 输出 JSON，不要输出 Markdown
7. 要考虑知识点的前置依赖关系"""


def build_learning_path_messages(
    student_id: str,
    grade: str,
    target_score: int | None,
    current_score: int | None,
    weak_points: list[dict],
    error_types: dict[str, int],
    recent_records: list[dict],
    prerequisite_map: dict[str, list[str]],
) -> list[dict]:
    return [
        {"role": "system", "content": LEARNING_PATH_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【学生 ID】\n{student_id}\n\n"
                f"【年级】\n{grade}\n\n"
                f"【目标分数】\n{target_score or '未设定'}\n\n"
                f"【当前分数】\n{current_score or '未设定'}\n\n"
                f"【薄弱知识点（按错误次数排序）】\n"
                + (
                    "\n".join(
                        f"- {p['name']}：错误 {p['count']} 次"
                        for p in weak_points[:8]
                    )
                    or "暂无记录"
                )
                + "\n\n"
                f"【错误类型分布】\n"
                + (
                    "\n".join(f"- {k}: {v} 次" for k, v in error_types.items())
                    or "暂无记录"
                )
                + "\n\n"
                f"【知识点前置依赖】\n"
                + (
                    "\n".join(
                        f"- {k} → 前置: {', '.join(v)}"
                        for k, v in prerequisite_map.items()
                        if v
                    )
                    or "无"
                )
                + "\n\n"
                f"【近期错题记录（最近 5 条）】\n"
                + (
                    "\n".join(
                        f"- {r.get('question_text', '')[:80]}... 错因: {r.get('error_type', '未知')}"
                        for r in recent_records[:5]
                    )
                    or "暂无记录"
                )
            ),
        },
    ]
