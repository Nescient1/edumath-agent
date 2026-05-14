from pydantic import BaseModel, Field

from app.schemas.diagnose import SimilarQuestion


class RecommendRequest(BaseModel):
    knowledge_points: list[str]
    difficulty: str | None = None
    count: int = Field(default=3, ge=1, le=10)


class RecommendResponse(BaseModel):
    questions: list[SimilarQuestion]
