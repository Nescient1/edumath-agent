import re

from app.repositories.question_repository import get_question
from app.schemas.practice import PracticeAnswerRequest, PracticeAnswerResponse
from app.services.profile_service import update_student_profile


KEYWORD_POOL = [
    "定义域",
    "求导",
    "导数",
    "临界点",
    "单调",
    "递增",
    "递减",
    "极大值",
    "极小值",
    "最大值",
    "最小值",
    "切线",
    "斜率",
    "零点",
    "端点",
    "符号",
    "参数",
]


def _extract_keywords(text: str) -> list[str]:
    found = [keyword for keyword in KEYWORD_POOL if keyword in text]
    math_tokens = re.findall(r"[A-Za-z]\s*=\s*[-+]?\d+|[-+]?\d+", text)
    return sorted(set(found + [token.replace(" ", "") for token in math_tokens]))


def grade_practice_answer(req: PracticeAnswerRequest) -> PracticeAnswerResponse:
    question = get_question(req.question_id)
    if question is None:
        raise ValueError("题目不存在")

    reference_text = f"{question.answer}\n{question.solution}"
    expected_keywords = _extract_keywords(reference_text)
    student_keywords = _extract_keywords(req.student_answer)
    matched = [keyword for keyword in expected_keywords if keyword in student_keywords]
    missed = [keyword for keyword in expected_keywords if keyword not in student_keywords]

    if not expected_keywords:
        score = 60 if req.student_answer.strip() else 0
    else:
        score = round(len(matched) / len(expected_keywords) * 100)

    score = min(100, max(0, score))
    is_correct = score >= 75

    if is_correct:
        feedback = "作答覆盖了主要步骤和结论，可以继续练一道稍有变化的题。"
    elif score >= 45:
        feedback = "思路有一部分是对的，但关键步骤或最终结论还不完整。"
        update_student_profile(req.student_id, question.knowledge_points, "步骤不完整")
    else:
        feedback = "当前答案和参考解法差距较大，建议先回到知识点讲义补齐方法。"
        update_student_profile(req.student_id, question.knowledge_points, "方法选择错误")

    return PracticeAnswerResponse(
        question_id=question.id,
        score=score,
        is_correct=is_correct,
        feedback=feedback,
        reference_answer=question.answer,
        matched_keywords=matched,
        missed_keywords=missed[:8],
        knowledge_points=question.knowledge_points,
    )
