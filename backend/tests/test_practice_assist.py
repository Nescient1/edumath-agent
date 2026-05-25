from app.schemas.practice import PracticeAssistRequest
from app.services.grading_service import assist_practice


def test_practice_assist_no_idea_returns_hint():
    response = assist_practice(
        PracticeAssistRequest(
            student_id="TEST_PRACTICE",
            question_id="Q001",
            student_input="我只会求导，后面没思路",
            mode="auto",
        )
    )

    assert response.mode == "hint"
    assert response.next_step
    assert "导数" in response.message


def test_practice_assist_answer_mode_returns_reference_answer():
    response = assist_practice(
        PracticeAssistRequest(
            student_id="TEST_PRACTICE",
            question_id="Q001",
            mode="answer",
        )
    )

    assert response.mode == "answer"
    assert response.reference_answer


def test_practice_assist_grade_mode_returns_score():
    response = assist_practice(
        PracticeAssistRequest(
            student_id="TEST_PRACTICE",
            question_id="Q001",
            student_input="f'(x)=3x^2-3，临界点 x=-1 和 x=1，判断导数符号得到单调区间和极值。",
            mode="grade",
        )
    )

    assert response.mode == "grade"
    assert response.score is not None
    assert response.feedback
