from pydantic import BaseModel, Field

from app.schemas.diagnose import SimilarQuestion
from app.schemas.question import GeneratedQuestion


class RecommendRequest(BaseModel):
    knowledge_points: list[str]
    difficulty: str | None = None
    count: int = Field(default=3, ge=1, le=10)


class RecommendResponse(BaseModel):
    questions: list[SimilarQuestion]


class VariantRequest(BaseModel):
    question_text: str
    knowledge_points: list[str]
    difficulty: str = "中等"
    count: int = Field(default=3, ge=1, le=6)


class VariantResponse(BaseModel):
    questions: list[GeneratedQuestion]
