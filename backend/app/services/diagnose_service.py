import json
import re

from app.core.config import settings
from app.prompts.explain_prompt import (
    build_pitfalls_messages,
    build_step_messages,
    build_strategy_messages,
)
from app.schemas.diagnose import (
    DiagnoseRequest,
    DiagnoseResponse,
    SourceSummary,
    StepExplanation,
)
from app.services.knowledge_service import identify_knowledge_points, infer_difficulty
from app.services.llm_service import is_enabled_flag, is_llm_enabled, safe_generate_text
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


def _compact_context(text: str, limit: int = 3500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _parse_llm_json(content: str | None) -> dict:
    if not content:
        return {}

    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def _coerce_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, list):
                result.extend(_coerce_string_list(item))
            else:
                text = str(item).strip()
                if text:
                    result.append(text)
        return result
    if isinstance(value, str) and value.strip():
        return [line.strip("- \n") for line in value.splitlines() if line.strip()]
    return []


def _maybe_generate_llm_diagnosis(
    *,
    question_text: str,
    student_answer: str | None,
    intent: str,
    knowledge_points: list[str],
    error_type: str,
    answer_mode: str,
    retrieval_quality: str,
    context_text: str,
    source_summary: list[SourceSummary],
    similar_questions: list,
    rule_diagnosis: str,
    rule_explanation: str,
    rule_concepts: list[str],
) -> tuple[str, str, list[str]]:
    if not is_enabled_flag(settings.enable_llm_diagnose) or not is_llm_enabled():
        return rule_diagnosis, rule_explanation, rule_concepts

    source_payload = [item.model_dump() for item in source_summary]
    question_payload = [
        {
            "id": item.id,
            "difficulty": item.difficulty,
            "question_type": item.question_type,
            "knowledge_points": item.knowledge_points,
            "question_text": item.question_text[:220],
        }
        for item in similar_questions
    ]
    solving_extra = ""
    if intent == INTENT_QUESTION_SOLVING and retrieval_quality in {"low", "none"}:
        solving_extra = (
            "当前 RAG 命中较低，请基于通用高中数学方法完整求解，"
            "写出解题步骤、关键公式、容易错的地方。"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "你是 EduMath Agent 的高中数学个性化家教。"
                "请基于给定结构化信息生成诊断，不要编造资料来源。"
                "如果知识库命中低，要明确说明主要基于通用数学方法。"
                "如果 material_query 且 no_source，要说明当前知识库未找到对应资料。"
                "如果 question_recommend，只能引用题库推荐题，不能把讲义片段当题。"
                "输出 JSON，不要输出 Markdown。字段为 diagnosis, explanation, key_concepts。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question_text": question_text,
                    "student_answer": student_answer or "",
                    "intent": intent,
                    "knowledge_points": knowledge_points,
                    "error_type": error_type,
                    "answer_mode": answer_mode,
                    "retrieval_quality": retrieval_quality,
                    "rag_context_text": _compact_context(context_text),
                    "source_summary": source_payload,
                    "similar_questions_from_questions_json": question_payload,
                    "rule_diagnosis": rule_diagnosis,
                    "rule_explanation": rule_explanation,
                    "rule_key_concepts": rule_concepts,
                    "extra_instruction": solving_extra,
                },
                ensure_ascii=False,
            ),
        },
    ]
    content = safe_generate_text(
        messages=messages,
        max_tokens=settings.llm_max_tokens,
        temperature=0.2,
        fallback=None,
    )
    data = _parse_llm_json(content)
    diagnosis = str(data.get("diagnosis") or rule_diagnosis).strip()
    explanation = str(data.get("explanation") or rule_explanation).strip()
    concepts = _coerce_string_list(data.get("key_concepts")) or rule_concepts
    return diagnosis, explanation, concepts[:6]


def _infer_error_type(
    student_answer: str | None,
    knowledge_points: list[str] | None = None,
    difficulty: str | None = None,
) -> str:
    answer = student_answer or ""
    if not answer.strip():
        if difficulty == "困难":
            return "综合应用不足"
        if any(
            p in (knowledge_points or [])
            for p in ["含参函数讨论", "导数证明不等式"]
        ):
            return "方法选择错误"
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


def _generate_step_explanation(
    question_text: str,
    knowledge_points: list[str],
    context_text: str,
    error_type: str,
) -> list[StepExplanation]:
    if not is_enabled_flag(settings.enable_llm_diagnose) or not is_llm_enabled():
        return _rule_step_explanation(knowledge_points)
    messages = build_step_messages(question_text, knowledge_points, context_text, error_type)
    content = safe_generate_text(
        messages=messages,
        max_tokens=1200,
        temperature=0.2,
        fallback=None,
    )
    data = _parse_llm_json(content)
    raw = data.get("steps") if isinstance(data.get("steps"), list) else None
    if raw is None and isinstance(data, list):
        raw = data
    if not raw:
        return _rule_step_explanation(knowledge_points)
    steps = []
    for i, item in enumerate(raw[:6], start=1):
        if isinstance(item, dict):
            steps.append(
                StepExplanation(
                    step_number=i,
                    title=str(item.get("title", f"第{i}步")),
                    content=str(item.get("content", "")),
                )
            )
    return steps or _rule_step_explanation(knowledge_points)


def _rule_step_explanation(knowledge_points: list[str]) -> list[StepExplanation]:
    main = knowledge_points[0] if knowledge_points else "函数与导数"
    return [
        StepExplanation(step_number=1, title="审题", content=f"本题考查{main}，需要从题目条件中提取关键信息。"),
        StepExplanation(step_number=2, title="思路", content=f"确定研究对象后，运用{main}的标准方法求解。"),
        StepExplanation(step_number=3, title="步骤", content="按规范步骤完成计算，注意每一步的逻辑衔接。"),
        StepExplanation(step_number=4, title="总结", content="写出完整结论，检查定义域、端点等容易遗漏的细节。"),
    ]


def _generate_general_strategy(
    knowledge_points: list[str],
    error_type: str,
) -> str:
    if not is_enabled_flag(settings.enable_llm_diagnose) or not is_llm_enabled():
        return _rule_general_strategy(knowledge_points)
    messages = build_strategy_messages(knowledge_points, error_type)
    content = safe_generate_text(
        messages=messages,
        max_tokens=500,
        temperature=0.2,
        fallback=None,
    )
    if content and len(content) > 10:
        return content.strip()
    return _rule_general_strategy(knowledge_points)


def _rule_general_strategy(knowledge_points: list[str]) -> str:
    main = knowledge_points[0] if knowledge_points else "函数与导数"
    return (
        f"遇到{main}相关题目，先审清题意确定研究对象，"
        f"再选择对应的公式或性质进行推导，"
        f"最后检查结论的完整性和定义域限制。"
    )


def _generate_common_pitfalls(
    knowledge_points: list[str],
    error_type: str,
) -> list[str]:
    if not is_enabled_flag(settings.enable_llm_diagnose) or not is_llm_enabled():
        return _rule_common_pitfalls(knowledge_points)
    messages = build_pitfalls_messages(knowledge_points, error_type)
    content = safe_generate_text(
        messages=messages,
        max_tokens=500,
        temperature=0.2,
        fallback=None,
    )
    data = _parse_llm_json(content)
    pitfalls = _coerce_string_list(data.get("pitfalls"))
    if not pitfalls and isinstance(data, list):
        pitfalls = _coerce_string_list(data)
    if pitfalls:
        return pitfalls[:5]
    return _rule_common_pitfalls(knowledge_points)


def _rule_common_pitfalls(knowledge_points: list[str]) -> list[str]:
    pitfalls_map = {
        "函数定义域": ["忽略对数真数大于 0、根式非负、分母不为 0 的限制"],
        "导数计算": ["混淆 f'(x) 和 f'(x₀)，求导后忘记继续分析符号"],
        "导数与函数单调性": ["只求导不判断符号，或把临界点直接当作单调区间端点"],
        "导数与极值": ["把 f'(x)=0 的点直接当极值点，忽略符号变化判断"],
        "导数与最值": ["闭区间最值忘记比较端点值，只看极值"],
        "含参函数讨论": ["含参问题漏掉临界情况，讨论不完整"],
    }
    result: list[str] = []
    for p in knowledge_points:
        if p in pitfalls_map:
            result.extend(pitfalls_map[p])
    if not result:
        result = ["注意审清题意，不要遗漏定义域和端点条件"]
    return result[:5]


def diagnose_wrong_question(req: DiagnoseRequest) -> DiagnoseResponse:
    knowledge_points = identify_knowledge_points(req.question_text)
    difficulty = infer_difficulty(req.question_text, knowledge_points)
    error_type = _infer_error_type(req.student_answer, knowledge_points, difficulty)
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
    source_summary = [
        SourceSummary(
            title=source.title,
            source=source.source,
            content_type=source.content_type,
            score=source.score,
        )
        for source in retrieval_decision.sources
    ]
    diagnosis, explanation, concepts = _maybe_generate_llm_diagnosis(
        question_text=req.question_text,
        student_answer=req.student_answer,
        intent=intent_result.intent,
        knowledge_points=knowledge_points,
        error_type=error_type,
        answer_mode=retrieval_decision.answer_mode,
        retrieval_quality=retrieval_decision.retrieval_quality,
        context_text=retrieval_decision.context_text,
        source_summary=source_summary,
        similar_questions=similar_questions,
        rule_diagnosis=diagnosis,
        rule_explanation=explanation,
        rule_concepts=concepts,
    )

    step_explanation = _generate_step_explanation(
        req.question_text, knowledge_points, retrieval_decision.context_text, error_type,
    )
    general_strategy = _generate_general_strategy(knowledge_points, error_type)
    common_pitfalls = _generate_common_pitfalls(knowledge_points, error_type)

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
        source_summary=source_summary,
        similar_questions=similar_questions,
        step_by_step_explanation=step_explanation,
        general_strategy=general_strategy,
        common_pitfalls=common_pitfalls,
    )
