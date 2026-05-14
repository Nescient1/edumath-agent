import json
from functools import lru_cache

from app.core.config import DATA_DIR, NOTES_DIR
from app.schemas.question import KnowledgePoint


KNOWLEDGE_PATH = DATA_DIR / "knowledge_points.json"


@lru_cache(maxsize=1)
def load_knowledge_points() -> list[KnowledgePoint]:
    if not KNOWLEDGE_PATH.exists():
        return []

    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as file:
        raw_points = json.load(file)

    return [KnowledgePoint(**item) for item in raw_points]


def load_note_documents() -> list[tuple[str, str]]:
    documents: list[tuple[str, str]] = []
    if not NOTES_DIR.exists():
        return documents

    for path in sorted(NOTES_DIR.glob("*.md")):
        documents.append((path.stem, path.read_text(encoding="utf-8")))

    return documents
