from pydantic import BaseModel
from typing import Optional


class DiagnoseRequest(BaseModel):
    student_id: str
    question_text: str
    student_answer: Optional[str] = None


class SimilarQuestion(BaseModel):
    id: str
    question_text: str
    knowledge_points: list[str]
    difficulty: str
    question_type: str


class SourceSummary(BaseModel):
    title: str
    source: str
    content_type: str
    score: float


class DiagnoseResponse(BaseModel):
    record_id: str
    intent: str
    answer_mode: str
    retrieval_quality: str
    knowledge_points: list[str]
    difficulty: str
    error_type: str
    diagnosis: str
    explanation: str
    key_concepts: list[str]
    retrieved_context: list[str]
    source_summary: list[SourceSummary]
    similar_questions: list[SimilarQuestion]
