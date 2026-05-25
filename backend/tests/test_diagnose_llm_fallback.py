from app.core.config import settings
from app.schemas.diagnose import DiagnoseRequest
from app.services.diagnose_service import diagnose_wrong_question


DERIVATIVE_QUERY = "\u5df2\u77e5 f(x)=xe^x\uff0c\u6c42\u5355\u8c03\u533a\u95f4"
RECOMMEND_QUERY = "\u63a8\u8350\u4e09\u9053\u5bfc\u6570\u5355\u8c03\u6027\u9898"


def test_diagnose_uses_rule_fallback_when_llm_fails(monkeypatch):
    settings.openai_api_key = "test-key"
    settings.openai_model = "mimo-v2.5"
    settings.enable_llm_diagnose = "1"

    def fail_llm(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.diagnose_service.safe_generate_text", fail_llm)

    response = diagnose_wrong_question(
        DiagnoseRequest(
            student_id="LLM_FAIL",
            question_text=DERIVATIVE_QUERY,
            student_answer="\u6211\u53ea\u4f1a\u6c42\u5bfc",
        )
    )

    assert response.diagnosis
    assert response.explanation
    assert response.key_concepts


def test_question_solving_low_retrieval_attempts_llm(monkeypatch):
    settings.openai_api_key = "test-key"
    settings.openai_model = "mimo-v2.5"
    settings.enable_llm_diagnose = "1"
    calls = {"count": 0}

    def fake_retrieve(*args, **kwargs):
        from app.services.rag_router_service import RetrievalDecision

        return RetrievalDecision(
            answer_mode="llm_fallback",
            retrieval_quality="none",
            required_content_types=["knowledge_note"],
            sources=[],
            context_text="",
        )

    def fake_llm(*args, **kwargs):
        calls["count"] += 1
        return (
            '{"diagnosis":"LLM diagnosis","explanation":"LLM solving steps",'
            '"key_concepts":["LLM concept"]}'
        )

    monkeypatch.setattr("app.services.diagnose_service.retrieve_by_intent", fake_retrieve)
    monkeypatch.setattr("app.services.diagnose_service.safe_generate_text", fake_llm)

    response = diagnose_wrong_question(
        DiagnoseRequest(
            student_id="LLM_SOLVE",
            question_text=DERIVATIVE_QUERY,
            student_answer="",
        )
    )

    assert calls["count"] == 1
    assert response.answer_mode == "llm_fallback"
    assert response.diagnosis == "LLM diagnosis"
    assert response.explanation == "LLM solving steps"
    assert response.key_concepts == ["LLM concept"]


def test_question_recommend_still_uses_question_bank():
    response = diagnose_wrong_question(
        DiagnoseRequest(
            student_id="RECOMMEND_BANK",
            question_text=RECOMMEND_QUERY,
            student_answer="",
        )
    )

    assert response.intent == "question_recommend"
    assert response.similar_questions
    assert all(item.id for item in response.similar_questions)
