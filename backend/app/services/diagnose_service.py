from app.schemas.diagnose import DiagnoseRequest, DiagnoseResponse, SourceSummary
from app.services.knowledge_service import identify_knowledge_points, infer_difficulty
from app.services.profile_service import (
    save_wrong_question_record,
    update_student_profile,
)
from app.services.query_router_service import (
    INTENT_MATERIAL_QUERY,
    INTENT_QUESTION_RECOMMEND,
    INTENT_QUESTION_SOLVING,
    classify_query_intent,
)
from app.services.rag_router_service import retrieve_by_intent
from app.services.recommend_service import recommend_similar_questions


def _infer_error_type(student_answer: str | None) -> str:
    answer = student_answer or ""
    if not answer.strip():
        return "步骤不完整"
    if "只求导" in answer or "不知道后面" in answer or "不会继续" in answer:
        return "步骤不完整"
    if "算错" in answer or "计算" in answer or "符号错" in answer:
        return "计算错误"
    if "公式" in answer or "记错" in answer:
        return "公式使用错误"
    if "看错" in answer or "审题" in answer:
        return "审题错误"
    if "不会" in answer or "没思路" in answer:
        return "方法选择错误"
    return "综合应用不足"


def _build_diagnosis(
    knowledge_points: list[str],
    error_type: str,
    student_answer: str | None,
) -> str:
    main_point = knowledge_points[0] if knowledge_points else "函数与导数"
    if error_type == "步骤不完整":
        return f"你已经碰到了“{main_point}”的关键步骤，但解题链条还没有从条件推进到结论。"
    if error_type == "计算错误":
        return f"主要问题在“{main_point}”相关计算或符号判断上，需要把临界点和区间符号表写完整。"
    if error_type == "公式使用错误":
        return f"需要先校准“{main_point}”的核心公式或结论，再代入题目条件。"
    if not student_answer:
        return f"这题重点考查“{main_point}”，当前缺少解题过程，因此先按标准步骤补齐。"
    return f"这题涉及“{main_point}”，你的思路还需要把知识点、条件转化和结论表达连起来。"


def _build_explanation(
    question_text: str,
    knowledge_points: list[str],
    context: list[str],
) -> str:
    steps = []
    if "函数定义域" in knowledge_points:
        steps.append("先写出使解析式有意义的条件，例如根式非负、对数真数大于 0、分母不为 0。")
    if "导数计算" in knowledge_points:
        steps.append("先准确求出导函数，化简成便于判断符号或求临界点的形式。")
    if "导数与函数单调性" in knowledge_points or "函数单调性" in knowledge_points:
        steps.append("令导数等于 0 或找出关键分界点，用这些点划分区间，再判断每个区间的符号。")
    if "导数与极值" in knowledge_points:
        steps.append("观察导数符号在临界点两侧的变化：由正变负是极大值，由负变正是极小值。")
    if "导数与最值" in knowledge_points:
        steps.append("如果题目给了闭区间，要同时比较端点值和区间内部极值。")
    if "导数几何意义" in knowledge_points:
        steps.append("切线问题先找切点，再用导数求斜率，最后代入点斜式写切线方程。")
    if "含参函数讨论" in knowledge_points:
        steps.append("含参问题要把参数影响的临界点、判别式或导数符号分情况讨论。")
    if "函数零点" in knowledge_points:
        steps.append("零点问题常用单调性和函数值符号变化判断个数。")
    if "导数证明不等式" in knowledge_points:
        steps.append("证明不等式时，可以把两边移到同一侧构造函数，再用导数研究单调性或最值。")

    if not steps:
        steps.append("先把题目条件翻译成函数性质，再选择定义域、单调性、极值或图像方法推进。")

    reference_hint = ""
    if context:
        reference_hint = "本次检索到的讲义也强调：先确定研究对象，再用定义域、导数符号或端点比较完成判断。"

    return " ".join(
        [
            f"这道题可以按“{knowledge_points[0] if knowledge_points else '函数与导数'}”的标准流程处理。",
            *steps,
            "最后把区间、极值点、极值或结论写完整，注意端点和定义域不能遗漏。",
            reference_hint,
        ]
    ).strip()


def _key_concepts(knowledge_points: list[str]) -> list[str]:
    concept_map = {
        "函数定义域": "解析式有意义是讨论函数性质的前提。",
        "函数单调性": "单调性描述自变量增大时函数值的变化趋势。",
        "导数计算": "求导后要继续服务于符号判断、切线斜率或最值比较。",
        "导数几何意义": "函数在某点的导数等于该点切线斜率。",
        "导数与函数单调性": "在区间内 f'(x)>0 函数递增，f'(x)<0 函数递减。",
        "导数与极值": "极值点要看导数符号是否在该点两侧发生变化。",
        "导数与最值": "闭区间最值要比较端点值和内部极值。",
        "函数零点": "连续函数的零点个数常结合单调性和端点函数值判断。",
        "含参函数讨论": "含参题要按参数导致的临界情况分类。",
        "导数证明不等式": "构造函数后用导数证明单调性或求最值，是不等式证明的常见路线。",
    }
    concepts = [concept_map[point] for point in knowledge_points if point in concept_map]
    return concepts[:5] or ["先明确考点，再选择对应的函数性质工具。"]


def diagnose_wrong_question(req: DiagnoseRequest) -> DiagnoseResponse:
    knowledge_points = identify_knowledge_points(req.question_text)
    difficulty = infer_difficulty(req.question_text, knowledge_points)
    error_type = _infer_error_type(req.student_answer)
    intent_query = f"{req.question_text}\n{req.student_answer or ''}".strip()
    intent_result = classify_query_intent(intent_query)
    retrieval_decision = retrieve_by_intent(
        query=req.question_text,
        intent=intent_result.intent,
        knowledge_points=knowledge_points,
        k=5,
    )
    context = [retrieval_decision.context_text] if retrieval_decision.context_text else []
    similar_questions = recommend_similar_questions(
        knowledge_points=knowledge_points,
        difficulty=difficulty,
        count=3,
        exclude_text=req.question_text,
    )

    diagnosis = _build_diagnosis(knowledge_points, error_type, req.student_answer)
    explanation = _build_explanation(req.question_text, knowledge_points, context)
    if (
        intent_result.intent == INTENT_MATERIAL_QUERY
        and retrieval_decision.answer_mode == "no_source"
    ):
        explanation = "当前知识库未找到对应资料，我可以先基于通用高中数学方法说明这道题。"
    elif (
        intent_result.intent == INTENT_QUESTION_SOLVING
        and retrieval_decision.answer_mode == "llm_fallback"
    ):
        explanation = f"{explanation} 当前知识库命中较低，因此这部分讲解主要使用通用数学方法。"
    elif intent_result.intent == INTENT_QUESTION_RECOMMEND:
        diagnosis = "已根据识别到的知识点从本地题库中筛选相似练习题。"
        explanation = "推荐题严格来自结构化题库，不会把讲义片段当作题目。"
    concepts = _key_concepts(knowledge_points)

    update_student_profile(req.student_id, knowledge_points, error_type)
    record_id = save_wrong_question_record(
        student_id=req.student_id,
        question_text=req.question_text,
        student_answer=req.student_answer,
        knowledge_points=knowledge_points,
        error_type=error_type,
        diagnosis=diagnosis,
    )

    return DiagnoseResponse(
        record_id=record_id,
        intent=intent_result.intent,
        answer_mode=retrieval_decision.answer_mode,
        retrieval_quality=retrieval_decision.retrieval_quality,
        knowledge_points=knowledge_points,
        difficulty=difficulty,
        error_type=error_type,
        diagnosis=diagnosis,
        explanation=explanation,
        key_concepts=concepts,
        retrieved_context=context,
        source_summary=[
            SourceSummary(
                title=source.title,
                source=source.source,
                content_type=source.content_type,
                score=source.score,
            )
            for source in retrieval_decision.sources
        ],
        similar_questions=similar_questions,
    )
