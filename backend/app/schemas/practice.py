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


class PracticeAssistRequest(BaseModel):
    student_id: str
    question_id: str
    student_input: str = ""
    mode: str = "auto"
    recognized_answer: str | None = None
    ocr_image_path: str | None = None


class PracticeAssistResponse(BaseModel):
    question_id: str
    mode: str
    message: str
    next_step: str | None = None
    score: int | None = None
    is_correct: bool | None = None
    feedback: str | None = None
    reference_answer: str | None = None
    solution: str | None = None
    matched_keywords: list[str] = []
    missed_keywords: list[str] = []
    knowledge_points: list[str] = []
    attempt_id: str | None = None
    can_show_answer: bool = True
