from fastapi import APIRouter, HTTPException, Query

from app.schemas.learning_path import LearningPath
from app.schemas.profile import (
    ProfileAdvice,
    StudentProfile,
    StudentProfileUpdate,
    WrongQuestionRecord,
    WrongQuestionRecordUpdate,
)
from app.services.learning_path_service import generate_learning_path
from app.services.profile_service import (
    edit_student_profile,
    edit_wrong_record,
    get_student_profile,
    get_wrong_records,
    refresh_student_profile_advice,
)


router = APIRouter(tags=["profiles"])


@router.get("/profile/{student_id}", response_model=StudentProfile)
def profile(student_id: str):
    return get_student_profile(student_id)


@router.put("/profile/{student_id}", response_model=StudentProfile)
def update_profile(student_id: str, req: StudentProfileUpdate):
    return edit_student_profile(student_id, req)


@router.post("/profile/{student_id}/advice", response_model=ProfileAdvice)
def refresh_advice(student_id: str):
    return refresh_student_profile_advice(student_id)


@router.get("/profile/{student_id}/records", response_model=list[WrongQuestionRecord])
def wrong_records(
    student_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return get_wrong_records(student_id, limit=limit, offset=offset)


@router.patch(
    "/profile/{student_id}/records/{record_id}",
    response_model=WrongQuestionRecord,
)
def update_wrong_record(student_id: str, record_id: str, req: WrongQuestionRecordUpdate):
    record = edit_wrong_record(student_id, record_id, req)
    if record is None:
        raise HTTPException(status_code=404, detail="Wrong question record not found")
    return record


@router.get("/profile/{student_id}/learning-path", response_model=LearningPath)
def learning_path(student_id: str):
    return generate_learning_path(student_id)
