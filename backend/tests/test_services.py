from app.schemas.diagnose import DiagnoseRequest
from app.services.diagnose_service import diagnose_wrong_question
from app.services.knowledge_service import identify_knowledge_points


def test_identify_derivative_monotonicity():
    points = identify_knowledge_points("已知 f(x)=x^3-3x，求单调区间和极值")
    assert "导数与函数单调性" in points
    assert "导数与极值" in points


def test_diagnose_returns_similar_questions():
    response = diagnose_wrong_question(
        DiagnoseRequest(
            student_id="TEST",
            question_text="已知函数 f(x)=x^3-3x，求函数的单调区间和极值。",
            student_answer="我只求导，不知道后面怎么做。",
        )
    )
    assert response.knowledge_points
    assert response.similar_questions
