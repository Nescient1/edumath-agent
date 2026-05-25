STEP_BY_STEP_SYSTEM = """你是 EduMath Agent 的高中数学家教。
请按"审题→思路→步骤→总结"四步，对题目进行分步讲解。

要求：
1. 每一步包含 step_number、title、content 三个字段
2. 审题：提取题目关键条件和目标
3. 思路：说明解题方向和涉及的知识点
4. 步骤：写出完整的推导或计算过程
5. 总结：归纳结论和注意事项
6. 输出 JSON 数组，不要输出 Markdown
7. 语言通俗易懂，适合高中生阅读"""

GENERAL_STRATEGY_SYSTEM = """你是 EduMath Agent 的高中数学家教。
请基于学生的错误类型和考查知识点，总结这类题目的通用解题策略。

要求：
1. 策略要具有普适性，适用于同一类知识点的题目
2. 语言简洁，用"先...再...最后..."的结构
3. 输出纯文本，不超过 200 字
4. 不要输出 Markdown"""

COMMON_PITFALLS_SYSTEM = """你是 EduMath Agent 的高中数学家教。
请基于题目考查的知识点和学生的错误类型，列出该类题目最常见的 3-5 个易错点。

要求：
1. 每个易错点用一句话描述
2. 输出 JSON 数组，元素为字符串
3. 不要输出 Markdown
4. 语言简洁，适合高中生阅读"""


def build_step_messages(
    question_text: str,
    knowledge_points: list[str],
    context_text: str,
    error_type: str,
) -> list[dict]:
    return [
        {"role": "system", "content": STEP_BY_STEP_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【题目】\n{question_text}\n\n"
                f"【知识点】\n{', '.join(knowledge_points)}\n\n"
                f"【错误类型】\n{error_type}\n\n"
                f"【参考讲义】\n{context_text[:2000]}"
            ),
        },
    ]


def build_strategy_messages(
    knowledge_points: list[str],
    error_type: str,
) -> list[dict]:
    return [
        {"role": "system", "content": GENERAL_STRATEGY_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【知识点】\n{', '.join(knowledge_points)}\n\n"
                f"【学生错误类型】\n{error_type}"
            ),
        },
    ]


def build_pitfalls_messages(
    knowledge_points: list[str],
    error_type: str,
) -> list[dict]:
    return [
        {"role": "system", "content": COMMON_PITFALLS_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【知识点】\n{', '.join(knowledge_points)}\n\n"
                f"【学生错误类型】\n{error_type}"
            ),
        },
    ]
