from dataclasses import dataclass


INTENT_CONCEPT_EXPLAIN = "concept_explain"
INTENT_WRONG_QUESTION_DIAGNOSE = "wrong_question_diagnose"
INTENT_QUESTION_SOLVING = "question_solving"
INTENT_QUESTION_RECOMMEND = "question_recommend"
INTENT_PROFILE_ADVICE = "profile_advice"
INTENT_MATERIAL_QUERY = "material_query"
INTENT_UNKNOWN = "unknown"


@dataclass
class QueryIntentResult:
    intent: str
    confidence: float
    matched_keywords: list[str]


INTENT_KEYWORDS = {
    INTENT_QUESTION_RECOMMEND: ["推荐", "练几道", "出题", "练习题", "相似题", "刷题"],
    INTENT_PROFILE_ADVICE: ["我的薄弱点", "薄弱点", "学习建议", "学习规划", "画像", "掌握情况"],
    INTENT_MATERIAL_QUERY: ["讲义", "教材", "第几章", "资料里", "课程标准", "课件"],
    INTENT_WRONG_QUESTION_DIAGNOSE: ["错因", "我错在哪", "为什么错", "错在哪里", "错题", "不会继续", "只会求导"],
    INTENT_CONCEPT_EXPLAIN: ["怎么理解", "是什么", "公式", "方法", "概念", "定理", "如何判断"],
    INTENT_QUESTION_SOLVING: ["已知", "求", "证明", "函数 f(x)", "f(x)", "单调区间", "极值", "最值"],
}


def classify_query_intent(query: str) -> QueryIntentResult:
    text = query.strip()
    if not text:
        return QueryIntentResult(INTENT_UNKNOWN, 0.0, [])

    priority = [
        INTENT_QUESTION_RECOMMEND,
        INTENT_PROFILE_ADVICE,
        INTENT_MATERIAL_QUERY,
        INTENT_WRONG_QUESTION_DIAGNOSE,
        INTENT_CONCEPT_EXPLAIN,
        INTENT_QUESTION_SOLVING,
    ]

    best_intent = INTENT_UNKNOWN
    best_matches: list[str] = []
    for intent in priority:
        matches = [keyword for keyword in INTENT_KEYWORDS[intent] if keyword in text]
        if matches:
            best_intent = intent
            best_matches = matches
            break

    if best_intent == INTENT_UNKNOWN:
        return QueryIntentResult(INTENT_UNKNOWN, 0.1, [])

    confidence = min(0.95, 0.55 + len(best_matches) * 0.15)
    return QueryIntentResult(best_intent, confidence, best_matches)
