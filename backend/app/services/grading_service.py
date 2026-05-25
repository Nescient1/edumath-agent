import re
from uuid import uuid4

from app.repositories.practice_repository import add_practice_event, save_practice_attempt
from app.repositories.question_repository import get_question
from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeAssistRequest,
    PracticeAssistResponse,
)
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


NO_IDEA_PATTERNS = [
    "不会",
    "没思路",
    "没有思路",
    "不知道",
    "卡住",
    "只会",
    "求提示",
    "看不懂",
    "下一步",
]


def _wants_hint(text: str) -> bool:
    compact = text.replace(" ", "")
    return any(pattern in compact for pattern in NO_IDEA_PATTERNS)


def _first_step_hint(question_text: str, knowledge_points: list[str]) -> tuple[str, str]:
    point_text = "、".join(knowledge_points[:3]) or "当前知识点"
    if "导数" in point_text or "单调" in point_text or "极值" in point_text:
        return (
            f"这题先不要急着写完整答案。它主要考查 {point_text}，第一步先写定义域，再求导并找导数为 0 或不存在的点。",
            "下一步请你补一张导数符号表：按临界点把定义域分段，分别判断 f'(x) 的正负。",
        )
    if "切线" in point_text:
        return (
            f"这题主要考查 {point_text}。先确认切点横坐标，再用导数表示切线斜率。",
            "下一步请写出 k=f'(x0)，再套 y-y0=k(x-x0)。",
        )
    if "零点" in point_text:
        return (
            f"这题主要考查 {point_text}。先把问题转成函数图像与 x 轴交点，关注单调性和端点值。",
            "下一步请先列出函数的定义域、单调区间和关键点函数值。",
        )
    return (
        f"这题主要考查 {point_text}。先把题目条件整理成已知量、要求量和可用公式。",
        "下一步请先写出你能确定的第一条公式或性质，再继续推。",
    )


def _log_event(
    *,
    student_id: str,
    question_id: str,
    event_type: str,
    attempt_id: str | None = None,
    payload: dict | None = None,
) -> None:
    add_practice_event(
        {
            "id": str(uuid4()),
            "student_id": student_id,
            "question_id": question_id,
            "attempt_id": attempt_id,
            "event_type": event_type,
            "event_payload": payload or {},
        }
    )


def assist_practice(req: PracticeAssistRequest) -> PracticeAssistResponse:
    question = get_question(req.question_id)
    if question is None:
        raise ValueError("题目不存在")

    requested_mode = (req.mode or "auto").strip().lower()
    student_input = (req.recognized_answer or req.student_input or "").strip()
    if requested_mode == "auto":
        mode = "hint" if _wants_hint(student_input) or not student_input else "grade"
    elif requested_mode in {"grade", "hint", "answer", "solution"}:
        mode = requested_mode
    else:
        mode = "grade"

    if mode == "answer":
        _log_event(
            student_id=req.student_id,
            question_id=question.id,
            event_type="view_answer",
            payload={"question_type": question.question_type},
        )
        return PracticeAssistResponse(
            question_id=question.id,
            mode="answer",
            message="已显示参考答案。建议先对照自己卡住的位置，再看解析。",
            reference_answer=question.answer,
            knowledge_points=question.knowledge_points,
        )

    if mode == "solution":
        _log_event(
            student_id=req.student_id,
            question_id=question.id,
            event_type="view_solution",
            payload={"question_type": question.question_type},
        )
        return PracticeAssistResponse(
            question_id=question.id,
            mode="solution",
            message="已显示完整解析。看完后建议遮住解析，再独立复写关键步骤。",
            reference_answer=question.answer,
            solution=question.solution,
            knowledge_points=question.knowledge_points,
        )

    if mode == "hint":
        message, next_step = _first_step_hint(question.question_text, question.knowledge_points)
        attempt_id = str(uuid4())
        save_practice_attempt(
            {
                "id": attempt_id,
                "student_id": req.student_id,
                "question_id": question.id,
                "student_input": req.student_input,
                "ocr_image_path": req.ocr_image_path,
                "recognized_answer": req.recognized_answer,
                "feedback": message,
                "assist_mode": "hint",
                "metadata": {"next_step": next_step},
            }
        )
        _log_event(
            student_id=req.student_id,
            question_id=question.id,
            attempt_id=attempt_id,
            event_type="request_hint",
            payload={"student_input": req.student_input, "next_step": next_step},
        )
        return PracticeAssistResponse(
            question_id=question.id,
            mode="hint",
            message=message,
            next_step=next_step,
            feedback=message,
            knowledge_points=question.knowledge_points,
            attempt_id=attempt_id,
        )

    grade_response = grade_practice_answer(
        PracticeAnswerRequest(
            student_id=req.student_id,
            question_id=question.id,
            student_answer=student_input,
        )
    )
    attempt_id = str(uuid4())
    save_practice_attempt(
        {
            "id": attempt_id,
            "student_id": req.student_id,
            "question_id": question.id,
            "student_input": req.student_input,
            "ocr_image_path": req.ocr_image_path,
            "recognized_answer": req.recognized_answer,
            "score": grade_response.score,
            "is_correct": grade_response.is_correct,
            "feedback": grade_response.feedback,
            "assist_mode": "grade",
            "metadata": {
                "matched_keywords": grade_response.matched_keywords,
                "missed_keywords": grade_response.missed_keywords,
            },
        }
    )
    _log_event(
        student_id=req.student_id,
        question_id=question.id,
        attempt_id=attempt_id,
        event_type="submit_answer",
        payload={"score": grade_response.score, "is_correct": grade_response.is_correct},
    )
    return PracticeAssistResponse(
        question_id=grade_response.question_id,
        mode="grade",
        message="已完成批改。",
        score=grade_response.score,
        is_correct=grade_response.is_correct,
        feedback=grade_response.feedback,
        reference_answer=grade_response.reference_answer,
        matched_keywords=grade_response.matched_keywords,
        missed_keywords=grade_response.missed_keywords,
        knowledge_points=grade_response.knowledge_points,
        attempt_id=attempt_id,
    )
