import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.repositories.knowledge_repository import load_knowledge_points
from app.repositories.question_repository import load_questions


if __name__ == "__main__":
    questions = load_questions()
    knowledge_points = load_knowledge_points()
    print(f"Loaded {len(questions)} questions.")
    print(f"Loaded {len(knowledge_points)} knowledge points.")
