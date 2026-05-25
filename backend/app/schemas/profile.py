from pydantic import BaseModel


class WeakPoint(BaseModel):
    name: str
    count: int


class ProfileAdviceItem(BaseModel):
    title: str
    action: str


class ProfileWeeklyTask(BaseModel):
    day: str
    task: str


class ProfileAdvice(BaseModel):
    summary: str = ""
    priority_points: list[str] = []
    mistake_advice: list[ProfileAdviceItem] = []
    weekly_plan: list[ProfileWeeklyTask] = []
    generated_at: str | None = None


class StudentProfile(BaseModel):
    student_id: str
    name: str = ""
    grade: str = "高三"
    target_score: int = 120
    current_score: int | None = None
    textbook_version: str = ""
    current_topic: str = "函数与导数"
    learning_goal: str = ""
    weak_points: list[WeakPoint]
    error_types: dict[str, int] = {}
    mastery: dict[str, int | float | str | bool] = {}
    total_wrong_questions: int = 0
    recommendation: str
    llm_advice: str | None = None
    advice: ProfileAdvice | None = None
    updated_at: str | None = None


class StudentProfileUpdate(BaseModel):
    name: str | None = None
    grade: str | None = None
    target_score: int | None = None
    current_score: int | None = None
    textbook_version: str | None = None
    current_topic: str | None = None
    learning_goal: str | None = None
    weak_points: list[WeakPoint] | None = None
    error_types: dict[str, int] | None = None


class WrongQuestionRecord(BaseModel):
    id: str
    student_id: str
    question_text: str
    student_answer: str | None = None
    knowledge_points: list[str]
    error_type: str
    diagnosis: str
    review_status: str = "未复习"
    is_mastered: bool = False
    created_at: str
    updated_at: str | None = None


class WrongQuestionRecordUpdate(BaseModel):
    review_status: str | None = None
    is_mastered: bool | None = None
