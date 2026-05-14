from fastapi import APIRouter, HTTPException, Query

from app.repositories.question_repository import get_question, search_questions
from app.schemas.question import Question, QuestionSummary


router = APIRouter(tags=["questions"])


@router.get("/questions", response_model=list[QuestionSummary])
def list_questions(
    keyword: str | None = Query(default=None),
    knowledge_point: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
):
    questions = search_questions(
        keyword=keyword,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
    )
    return [
        QuestionSummary(
            id=item.id,
            question_text=item.question_text,
            knowledge_points=item.knowledge_points,
            difficulty=item.difficulty,
            question_type=item.question_type,
        )
        for item in questions
    ]


@router.get("/questions/{question_id}", response_model=Question)
def question_detail(question_id: str):
    question = get_question(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question
