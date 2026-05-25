import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import PROJECT_ROOT, settings
from app.main import app
from app.services.query_router_service import classify_query_intent
from app.services.rag_router_service import retrieve_by_intent


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    settings.enable_llm_diagnose = "0"
    os.environ["ENABLE_LLM_DIAGNOSE"] = "0"

    try:
        from fastapi.testclient import TestClient
    except ImportError as exc:
        raise RuntimeError("Missing fastapi test client dependencies.") from exc

    client = TestClient(app)

    questions_resp = client.get(
        "/api/questions",
        params={"knowledge_point": "导数与函数单调性"},
    )
    questions_resp.raise_for_status()
    questions = questions_resp.json()
    questions_with_images = [
        item for item in questions if item.get("image_urls") or item.get("image_paths")
    ]

    recommend_resp = client.post(
        "/api/recommend",
        json={
            "knowledge_points": ["导数与函数单调性"],
            "difficulty": "medium",
            "count": 5,
        },
    )
    recommend_resp.raise_for_status()
    recommended = recommend_resp.json()["questions"]

    diagnose_resp = client.post(
        "/api/diagnose",
        json={
            "student_id": "api-check",
            "question_text": "我只会求导但不会判断单调区间，导数如何判断函数单调性？",
            "student_answer": "我会求导，但是不知道怎么分区间。",
        },
    )
    diagnose_resp.raise_for_status()
    diagnosis = diagnose_resp.json()
    pg_query = "切线放缩法证明导数不等式怎么做"
    pg_intent = classify_query_intent(pg_query).intent
    pg_decision = retrieve_by_intent(
        pg_query,
        pg_intent,
        knowledge_points=["切线放缩", "导数证明不等式"],
        k=5,
    )
    pg_sources = [
        {
            "title": source.title,
            "content_type": source.content_type,
            "source": source.source,
            "source_path": source.source_path,
            "score": source.score,
        }
        for source in pg_decision.sources[:3]
    ]

    result = {
        "questions_by_knowledge_point": len(questions),
        "questions_with_images": len(questions_with_images),
        "sample_question": questions[0] if questions else None,
        "sample_question_with_image": questions_with_images[0]
        if questions_with_images
        else None,
        "recommended_count": len(recommended),
        "recommended_samples": recommended[:3],
        "diagnose": {
            "intent": diagnosis.get("intent"),
            "answer_mode": diagnosis.get("answer_mode"),
            "retrieval_quality": diagnosis.get("retrieval_quality"),
            "source_summary": diagnosis.get("source_summary", [])[:3],
            "similar_questions": diagnosis.get("similar_questions", [])[:3],
        },
        "postgres_rag_probe": {
            "query": pg_query,
            "intent": pg_intent,
            "answer_mode": pg_decision.answer_mode,
            "retrieval_quality": pg_decision.retrieval_quality,
            "sources": pg_sources,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not questions:
        raise SystemExit("/api/questions did not return database questions.")
    if not recommended:
        raise SystemExit("/api/recommend did not return recommended questions.")
    if diagnosis.get("retrieval_quality") not in {"high", "medium"}:
        raise SystemExit("/api/diagnose did not retrieve useful new RAG context.")
    if not any(
        "postgres" in item.get("source", "")
        for item in pg_sources
    ):
        raise SystemExit("RAG probe did not retrieve PostgreSQL-ingested materials.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
