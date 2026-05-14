from fastapi import APIRouter

from app.schemas.profile import StudentProfile, WrongQuestionRecord
from app.services.profile_service import get_student_profile, get_wrong_records


router = APIRouter(tags=["profiles"])


@router.get("/profile/{student_id}", response_model=StudentProfile)
def profile(student_id: str):
    return get_student_profile(student_id)


@router.get("/profile/{student_id}/records", response_model=list[WrongQuestionRecord])
def wrong_records(student_id: str):
    return get_wrong_records(student_id)
