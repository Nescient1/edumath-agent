VARIANT_GENERATION_SYSTEM = """你是 EduMath Agent 的高中数学出题专家。
请基于原题生成指定数量的变式题，保持同一知识点体系，难度有梯度。

要求：
1. 每道题包含：question_text（题目文本）、answer（标准答案）、solution（解题步骤）、difficulty（基础/中等/困难）、knowledge_points（知识点列表）、question_type（解答题/填空题/选择题）
2. 第 1 题为基础巩固（比原题简单），第 2 题为同类变式（与原题难度相当），第 3 题为综合提升（比原题难）
3. 题目要符合高中数学出题规范，不能出现超纲内容
4. 答案和解题步骤要完整准确
5. 输出 JSON 数组，不要输出 Markdown
6. 题目文本中数学表达式用 LaTeX 格式，如 $f(x)=x^2$"""


def build_variant_messages(
    question_text: str,
    knowledge_points: list[str],
    difficulty: str,
    count: int,
    example_questions: list[dict],
) -> list[dict]:
    example_text = ""
    if example_questions:
        example_text = "\n\n【参考题库示例（风格参考）】\n"
        for i, q in enumerate(example_questions[:3], 1):
            example_text += f"{i}. {q.get('question_text', '')[:120]}\n"

    return [
        {"role": "system", "content": VARIANT_GENERATION_SYSTEM},
        {
            "role": "user",
            "content": (
                f"【原题】\n{question_text}\n\n"
                f"【知识点】\n{', '.join(knowledge_points)}\n\n"
                f"【原题难度】\n{difficulty}\n\n"
                f"【需要生成】\n{count} 道变式题"
                f"{example_text}"
            ),
        },
    ]
