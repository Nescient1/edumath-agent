import json
from functools import lru_cache

from app.core.config import DATA_DIR
from app.schemas.question import Question


QUESTIONS_PATH = DATA_DIR / "questions.json"


@lru_cache(maxsize=1)
def load_questions() -> list[Question]:
    if not QUESTIONS_PATH.exists():
        return []

    with QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        raw_questions = json.load(file)

    return [Question(**item) for item in raw_questions]


def get_question(question_id: str) -> Question | None:
    return next((item for item in load_questions() if item.id == question_id), None)


def search_questions(
    keyword: str | None = None,
    knowledge_point: str | None = None,
    difficulty: str | None = None,
) -> list[Question]:
    keyword = keyword.strip() if keyword else None
    knowledge_point = knowledge_point.strip() if knowledge_point else None
    difficulty = difficulty.strip() if difficulty else None

    questions = load_questions()

    if keyword:
        questions = [
            item
            for item in questions
            if keyword in item.question_text
            or keyword in item.answer
            or keyword in item.solution
            or any(keyword in point for point in item.knowledge_points)
        ]

    if knowledge_point:
        questions = [
            item for item in questions if knowledge_point in item.knowledge_points
        ]

    if difficulty:
        questions = [item for item in questions if item.difficulty == difficulty]

    return questions
