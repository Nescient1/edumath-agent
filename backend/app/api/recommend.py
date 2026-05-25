from fastapi import APIRouter

from app.schemas.recommend import (
    RecommendRequest,
    RecommendResponse,
    VariantRequest,
    VariantResponse,
)
from app.services.question_generation_service import generate_variant_questions
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


@router.post("/recommend/variants", response_model=VariantResponse)
def recommend_variants(req: VariantRequest):
    return VariantResponse(
        questions=generate_variant_questions(
            question_text=req.question_text,
            knowledge_points=req.knowledge_points,
            difficulty=req.difficulty,
            count=req.count,
        )
    )
