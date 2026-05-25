import json


DIAGNOSE_SYSTEM = """你是 EduMath Agent 的高中数学个性化家教，专注于函数与导数专题。
请基于给定的结构化信息生成诊断，不要编造资料来源。

要求：
1. diagnosis：简洁说明学生错在哪里（1-2 句话）
2. explanation：适合高中生理解的讲解，包含解题思路和关键步骤
3. key_concepts：3-5 个关键知识点总结
4. 输出 JSON，不要输出 Markdown

特殊情况处理：
- 如果知识库命中较低，要说明主要基于通用数学方法
- 如果是 material_query 且无资料来源，要说明当前知识库未找到对应资料
- 如果是 question_recommend，只能引用题库推荐题，不能把讲义片段当题"""


def build_diagnose_messages(
    question_text: str,
    student_answer: str,
    intent: str,
    knowledge_points: list[str],
    error_type: str,
    answer_mode: str,
    retrieval_quality: str,
    context_text: str,
    source_summary: list[dict],
    similar_questions: list[dict],
    rule_diagnosis: str,
    rule_explanation: str,
    rule_concepts: list[str],
    extra_instruction: str = "",
) -> list[dict]:
    return [
        {"role": "system", "content": DIAGNOSE_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question_text": question_text,
                    "student_answer": student_answer or "",
                    "intent": intent,
                    "knowledge_points": knowledge_points,
                    "error_type": error_type,
                    "answer_mode": answer_mode,
                    "retrieval_quality": retrieval_quality,
                    "rag_context_text": context_text[:3500],
                    "source_summary": source_summary,
                    "similar_questions_from_questions_json": similar_questions,
                    "rule_diagnosis": rule_diagnosis,
                    "rule_explanation": rule_explanation,
                    "rule_key_concepts": rule_concepts,
                    "extra_instruction": extra_instruction,
                },
                ensure_ascii=False,
            ),
        },
    ]
