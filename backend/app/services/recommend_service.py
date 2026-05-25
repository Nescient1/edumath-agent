from app.repositories.question_repository import load_all_questions
from app.schemas.diagnose import SimilarQuestion


DIFFICULTY_ORDER = {
    "基础": 0,
    "easy": 0,
    "中等": 1,
    "medium": 1,
    "困难": 2,
    "hard": 2,
}


def _difficulty_matches(actual: str, target: str | None) -> bool:
    if not target:
        return False
    return actual == target or DIFFICULTY_ORDER.get(actual) == DIFFICULTY_ORDER.get(target)


def _is_complete_question(question) -> bool:
    return bool(question.question_text.strip()) and bool(
        question.answer.strip() or question.solution.strip()
    )


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
    questions = load_all_questions()
    scored = []

    for question in questions:
        if question.id in excluded_ids:
            continue
        if not _is_complete_question(question):
            continue
        if exclude_text and question.question_text.strip() == exclude_text.strip():
            continue

        overlap = target_points.intersection(question.knowledge_points)
        if not overlap:
            continue

        weak_overlap = weak_point_set.intersection(question.knowledge_points)
        difficulty_bonus = 3 if _difficulty_matches(question.difficulty, difficulty) else 0
        extracted_bonus = 2 if question.id.startswith("db:") else 0
        image_bonus = 1 if question.image_paths else 0
        score = (
            len(overlap) * 10
            + difficulty_bonus
            + len(weak_overlap) * 5
            + extracted_bonus
            + image_bonus
        )
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
            image_paths=item.image_paths,
            image_urls=item.image_urls,
            image_descriptions=item.image_descriptions,
        )
        for item in selected
    ]
