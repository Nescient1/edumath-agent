from pydantic import BaseModel


class PracticeAnswerRequest(BaseModel):
    student_id: str
    question_id: str
    student_answer: str


class PracticeAnswerResponse(BaseModel):
    question_id: str
    score: int
    is_correct: bool
    feedback: str
    reference_answer: str
    matched_keywords: list[str]
    missed_keywords: list[str]
    knowledge_points: list[str]
