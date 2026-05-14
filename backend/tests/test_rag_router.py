from app.schemas.diagnose import DiagnoseRequest
from app.services.diagnose_service import diagnose_wrong_question
from app.services.rag_router_service import (
    get_required_content_types,
    retrieve_by_intent,
)


def test_question_recommend_required_content_types():
    required = get_required_content_types("question_recommend")

    assert "question_card" in required
    assert "exercise" in required


def test_concept_explain_required_content_types():
    required = get_required_content_types("concept_explain")

    assert "knowledge_note" in required
    assert "lecture_note" in required


def test_retrieve_by_intent_without_vector_store_does_not_crash(monkeypatch):
    monkeypatch.setattr("app.services.rag_router_service._get_vector_store", lambda: None)

    decision = retrieve_by_intent(
        query="导数如何判断函数单调性",
        intent="concept_explain",
        knowledge_points=["导数与函数单调性"],
    )

    assert decision.answer_mode == "no_source"
    assert decision.retrieval_quality == "none"
    assert decision.sources == []


def test_diagnose_response_contains_router_fields():
    response = diagnose_wrong_question(
        DiagnoseRequest(
            student_id="ROUTER_TEST",
            question_text="已知 f(x)=xe^x，求单调区间",
            student_answer="我只会求导但不会判断单调区间",
        )
    )

    assert response.intent
    assert response.answer_mode
    assert response.retrieval_quality
    assert isinstance(response.source_summary, list)
