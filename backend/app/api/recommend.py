from fastapi import APIRouter

from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.recommend_service import recommend_similar_questions


router = APIRouter(tags=["recommend"])


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    return RecommendResponse(
        questions=recommend_similar_questions(
            knowledge_points=req.knowledge_points,
            difficulty=req.difficulty,
            count=req.count,
        )
    )
