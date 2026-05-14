from pydantic import BaseModel


class WeakPoint(BaseModel):
    name: str
    count: int


class StudentProfile(BaseModel):
    student_id: str
    grade: str = "高三"
    target_score: int = 120
    weak_points: list[WeakPoint]
    error_types: dict[str, int] = {}
    total_wrong_questions: int = 0
    recommendation: str
    updated_at: str | None = None


class WrongQuestionRecord(BaseModel):
    id: str
    student_id: str
    question_text: str
    student_answer: str | None = None
    knowledge_points: list[str]
    error_type: str
    diagnosis: str
    created_at: str
