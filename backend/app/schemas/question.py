from pydantic import BaseModel


class KnowledgePoint(BaseModel):
    id: str
    name: str
    chapter: str
    description: str
    prerequisites: list[str] = []
    common_exam_methods: list[str] = []
    keywords: list[str] = []


class Question(BaseModel):
    id: str
    question_text: str
    answer: str
    solution: str
    knowledge_points: list[str]
    difficulty: str
    question_type: str
    common_mistakes: list[str] = []


class QuestionSummary(BaseModel):
    id: str
    question_text: str
    knowledge_points: list[str]
    difficulty: str
    question_type: str
