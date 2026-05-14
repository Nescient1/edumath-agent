from app.repositories.question_repository import load_questions
from app.schemas.diagnose import SimilarQuestion


DIFFICULTY_ORDER = {"基础": 0, "中等": 1, "困难": 2}


def recommend_similar_questions(
    knowledge_points: list[str],
    difficulty: str | None = None,
    count: int = 3,
    exclude_text: str | None = None,
    weak_points: list[str] | None = None,
    exclude_question_ids: list[str] | None = None,
) -> list[SimilarQuestion]:
    target_points = set(knowledge_points)
    weak_point_set = set(weak_points or [])
    excluded_ids = set(exclude_question_ids or [])
    questions = load_questions()
    scored = []

    for question in questions:
        if question.id in excluded_ids:
            continue
        if exclude_text and question.question_text.strip() == exclude_text.strip():
            continue

        overlap = target_points.intersection(question.knowledge_points)
        if not overlap:
            continue

        weak_overlap = weak_point_set.intersection(question.knowledge_points)
        difficulty_bonus = 3 if difficulty and question.difficulty == difficulty else 0
        score = len(overlap) * 10 + difficulty_bonus + len(weak_overlap) * 5
        scored.append((score, question))

    scored.sort(
        key=lambda item: (
            -item[0],
            DIFFICULTY_ORDER.get(item[1].difficulty, 9),
            item[1].id,
        )
    )

    selected = [item[1] for item in scored[:count]]
    return [
        SimilarQuestion(
            id=item.id,
            question_text=item.question_text,
            knowledge_points=item.knowledge_points,
            difficulty=item.difficulty,
            question_type=item.question_type,
        )
        for item in selected
    ]
