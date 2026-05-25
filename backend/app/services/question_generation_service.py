from app.core.config import settings
from app.prompts.question_generation_prompt import build_variant_messages
from app.repositories.question_repository import load_all_questions
from app.schemas.question import GeneratedQuestion
from app.services.llm_service import is_enabled_flag, is_llm_enabled, safe_generate_text


def _parse_llm_json(content: str | None) -> dict | list | None:
    import json
    import re

    if not content:
        return None
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _seed_questions(
    knowledge_points: list[str],
    difficulty: str,
    exclude_text: str,
    count: int = 3,
) -> list[dict]:
    from app.services.recommend_service import _difficulty_matches, _is_complete_question

    target_points = set(knowledge_points)
    questions = load_all_questions()
    scored = []
    for q in questions:
        if not _is_complete_question(q):
            continue
        if q.question_text.strip() == exclude_text.strip():
            continue
        overlap = target_points.intersection(q.knowledge_points)
        if not overlap:
            continue
        bonus = 3 if _difficulty_matches(q.difficulty, difficulty) else 0
        scored.append((len(overlap) * 10 + bonus, q))

    scored.sort(key=lambda x: -x[0])
    return [
        {
            "question_text": q.question_text,
            "answer": q.answer,
            "solution": q.solution,
            "difficulty": q.difficulty,
            "knowledge_points": q.knowledge_points,
            "question_type": q.question_type,
            "source": "from_bank",
        }
        for _, q in scored[:count]
    ]


def _parse_generated_questions(raw: list) -> list[GeneratedQuestion]:
    result = []
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        qtext = str(item.get("question_text", "")).strip()
        if not qtext:
            continue
        result.append(
            GeneratedQuestion(
                question_text=qtext,
                answer=str(item.get("answer", "")),
                solution=str(item.get("solution", "")),
                difficulty=str(item.get("difficulty", "中等")),
                knowledge_points=[
                    str(k) for k in item.get("knowledge_points", []) if k
                ],
                question_type=str(item.get("question_type", "解答题")),
                source="generated",
            )
        )
    return result


def generate_variant_questions(
    question_text: str,
    knowledge_points: list[str],
    difficulty: str,
    count: int = 3,
) -> list[GeneratedQuestion]:
    seed = _seed_questions(knowledge_points, difficulty, question_text, count)

    if not is_enabled_flag(settings.enable_llm_question_generation) or not is_llm_enabled():
        return [
            GeneratedQuestion(**{k: v for k, v in s.items() if k != "source"}, source="from_bank")
            for s in seed
        ]

    messages = build_variant_messages(
        question_text, knowledge_points, difficulty, count, seed,
    )
    content = safe_generate_text(
        messages=messages,
        max_tokens=2000,
        temperature=0.3,
        fallback=None,
    )
    parsed = _parse_llm_json(content)
    if isinstance(parsed, list) and parsed:
        generated = _parse_generated_questions(parsed)
        if generated:
            return generated[:count]

    return [
        GeneratedQuestion(**{k: v for k, v in s.items() if k != "source"}, source="from_bank")
        for s in seed
    ]
