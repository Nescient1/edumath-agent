import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.query_router_service import classify_query_intent
from app.services.rag_router_service import retrieve_by_intent
from app.services.recommend_service import recommend_similar_questions


def main() -> int:
    queries = [
        ("我只会求导但不会判断单调区间", ["导数与函数单调性"]),
        ("推荐三道导数与函数单调性题", ["导数与函数单调性"]),
        ("曲线的切线方程怎么求", ["曲线的切线方程"]),
    ]
    for query, points in queries:
        intent = classify_query_intent(query).intent
        decision = retrieve_by_intent(query, intent, knowledge_points=points, k=5)
        print(f"\nQUERY: {query}")
        print(f"intent: {intent}")
        print(f"answer_mode: {decision.answer_mode}")
        print(f"retrieval_quality: {decision.retrieval_quality}")
        for source in decision.sources[:3]:
            print(
                "- "
                f"{source.content_type} | {source.title} | score={source.score} | "
                f"knowledge_points={source.knowledge_points[:4]}"
            )

    print("\nRECOMMEND:")
    items = recommend_similar_questions(["导数与函数单调性"], difficulty="medium", count=5)
    for item in items:
        preview = item.question_text[:90].replace("\n", " ")
        print(
            f"- {item.id} | {item.difficulty} | {item.question_type} | "
            f"{item.knowledge_points[:4]} | {preview}"
        )
    if not items:
        raise SystemExit("No recommended questions returned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
