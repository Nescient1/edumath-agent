from pydantic import BaseModel


class LearningPathTask(BaseModel):
    day: int
    knowledge_point: str
    task_type: str = "练习"
    questions: list[str] = []
    description: str


class LearningPathMilestone(BaseModel):
    day: int
    description: str
    checkpoints: list[str] = []


class LearningPath(BaseModel):
    student_id: str
    priority_order: list[str]
    daily_tasks: list[LearningPathTask]
    milestones: list[LearningPathMilestone]
    estimated_days: int = 7
    generated_at: str = ""
    source: str = "rule"
