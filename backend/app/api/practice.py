from fastapi import APIRouter, HTTPException

from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeAssistRequest,
    PracticeAssistResponse,
)
from app.services.grading_service import assist_practice, grade_practice_answer


router = APIRouter(tags=["practice"])


@router.post("/practice/grade", response_model=PracticeAnswerResponse)
def grade_practice(req: PracticeAnswerRequest):
    try:
        return grade_practice_answer(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/practice/assist", response_model=PracticeAssistResponse)
def assist_practice_answer(req: PracticeAssistRequest):
    try:
        return assist_practice(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
