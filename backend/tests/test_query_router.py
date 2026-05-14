from app.services.query_router_service import classify_query_intent


def test_question_recommend_intent():
    result = classify_query_intent("推荐三道导数单调性题")

    assert result.intent == "question_recommend"


def test_concept_explain_intent():
    result = classify_query_intent("导数如何判断函数单调性")

    assert result.intent == "concept_explain"


def test_question_solving_intent():
    result = classify_query_intent("已知 f(x)=xe^x，求单调区间")

    assert result.intent == "question_solving"
