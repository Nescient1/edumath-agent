from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import VECTOR_STORE_DIR
from app.services.embedding_service import (
    ensure_compatible_vector_store,
    read_embedding_config,
    resolve_embeddings,
)
from app.services.query_router_service import (
    INTENT_CONCEPT_EXPLAIN,
    INTENT_MATERIAL_QUERY,
    INTENT_PROFILE_ADVICE,
    INTENT_QUESTION_RECOMMEND,
    INTENT_QUESTION_SOLVING,
    INTENT_WRONG_QUESTION_DIAGNOSE,
)


ANSWER_RAG_STRONG = "rag_strong"
ANSWER_HYBRID = "hybrid"
ANSWER_LLM_FALLBACK = "llm_fallback"
ANSWER_NO_SOURCE = "no_source"

QUALITY_HIGH = "high"
QUALITY_MEDIUM = "medium"
QUALITY_LOW = "low"
QUALITY_NONE = "none"


CONTENT_TYPES_BY_INTENT = {
    INTENT_CONCEPT_EXPLAIN: ["knowledge_note", "lecture_note", "knowledge_summary"],
    INTENT_QUESTION_RECOMMEND: ["question_card", "exercise"],
    INTENT_WRONG_QUESTION_DIAGNOSE: ["error_rule", "common_mistake", "knowledge_note"],
    INTENT_MATERIAL_QUERY: ["official_standard", "lecture_note"],
    INTENT_QUESTION_SOLVING: ["knowledge_note", "lecture_note", "knowledge_summary"],
    INTENT_PROFILE_ADVICE: ["error_rule", "knowledge_note", "question_card"],
}


@dataclass
class RetrievedSource:
    title: str
    source: str
    source_path: str
    content_type: str
    section_type: str
    knowledge_points: list[str]
    score: float
    text: str
    quality_label: str = ""
    review_status: str = ""


@dataclass
class RetrievalDecision:
    answer_mode: str
    retrieval_quality: str
    required_content_types: list[str]
    sources: list[RetrievedSource]
    context_text: str


_VECTOR_STORE: Any = None


def get_required_content_types(intent: str) -> list[str]:
    return CONTENT_TYPES_BY_INTENT.get(intent, ["knowledge_note", "lecture_note"])


def _vector_store_exists() -> bool:
    return VECTOR_STORE_DIR.exists() and any(VECTOR_STORE_DIR.iterdir())


def _get_vector_store() -> Any:
    global _VECTOR_STORE
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE
    if not _vector_store_exists() or read_embedding_config(VECTOR_STORE_DIR) is None:
        return None

    try:
        from langchain_chroma import Chroma
    except ImportError:
        return None

    embeddings, embedding_config = resolve_embeddings()
    ensure_compatible_vector_store(embedding_config, VECTOR_STORE_DIR)
    _VECTOR_STORE = Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=embeddings,
    )
    return _VECTOR_STORE


def _split_knowledge_points(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    return [
        item.strip()
        for item in str(value).replace("，", ",").split(",")
        if item.strip()
    ]


def _source_from_result(doc: Any, score: float) -> RetrievedSource:
    metadata = getattr(doc, "metadata", {}) or {}
    source_path = metadata.get("source_path") or metadata.get("source") or ""
    title = metadata.get("title") or Path(source_path).stem or "unknown"
    content_type = (
        metadata.get("content_type")
        or metadata.get("doc_type")
        or metadata.get("source_type")
        or "unknown"
    )
    return RetrievedSource(
        title=str(title),
        source=str(metadata.get("source") or title),
        source_path=str(source_path),
        content_type=str(content_type),
        section_type=str(metadata.get("section_type") or ""),
        knowledge_points=_split_knowledge_points(metadata.get("knowledge_points")),
        score=float(score),
        text=str(getattr(doc, "page_content", "")).strip(),
        quality_label=str(metadata.get("quality_label") or ""),
        review_status=str(metadata.get("review_status") or ""),
    )


def _knowledge_matches(source: RetrievedSource, knowledge_points: list[str] | None) -> bool:
    if not knowledge_points:
        return True
    source_points = set(source.knowledge_points)
    target_points = set(knowledge_points)
    if source_points.intersection(target_points):
        return True
    joined_text = f"{source.title}\n{source.text}"
    return any(point in joined_text for point in knowledge_points)


def _is_usable_source(source: RetrievedSource) -> bool:
    if source.quality_label in {"low", "pending_review"}:
        return False
    if source.review_status in {
        "bad_split_cross_page",
        "incomplete_question",
        "exclude_from_recommendation",
    }:
        return False
    return True


def judge_retrieval_quality(
    results: list[RetrievedSource],
    intent: str,
    required_content_types: list[str],
    knowledge_points: list[str] | None = None,
) -> str:
    if not results:
        return QUALITY_NONE

    type_matched = [
        source for source in results if source.content_type in required_content_types
    ]
    if not type_matched:
        return QUALITY_LOW if intent == INTENT_QUESTION_SOLVING else QUALITY_NONE

    if any(_knowledge_matches(source, knowledge_points) for source in type_matched):
        return QUALITY_HIGH
    return QUALITY_MEDIUM


def _answer_mode_for_quality(intent: str, quality: str) -> str:
    if quality == QUALITY_HIGH:
        return ANSWER_RAG_STRONG
    if quality == QUALITY_MEDIUM:
        return ANSWER_HYBRID
    if quality == QUALITY_LOW and intent == INTENT_QUESTION_SOLVING:
        return ANSWER_LLM_FALLBACK
    if quality == QUALITY_NONE and intent in {
        INTENT_MATERIAL_QUERY,
        INTENT_QUESTION_RECOMMEND,
    }:
        return ANSWER_NO_SOURCE
    if quality == QUALITY_NONE and intent == INTENT_QUESTION_SOLVING:
        return ANSWER_LLM_FALLBACK
    return ANSWER_NO_SOURCE if quality == QUALITY_NONE else ANSWER_HYBRID


def _decision_without_source(intent: str, required: list[str]) -> RetrievalDecision:
    return RetrievalDecision(
        answer_mode=_answer_mode_for_quality(intent, QUALITY_NONE),
        retrieval_quality=QUALITY_NONE,
        required_content_types=required,
        sources=[],
        context_text="",
    )


def retrieve_by_intent(
    query: str,
    intent: str,
    knowledge_points: list[str] | None = None,
    k: int = 5,
) -> RetrievalDecision:
    required = get_required_content_types(intent)
    vector_store = None
    try:
        vector_store = _get_vector_store()
    except Exception:
        return _decision_without_source(intent, required)

    if vector_store is None:
        return _decision_without_source(intent, required)

    try:
        raw_results = vector_store.similarity_search_with_score(query, k=max(12, k))
    except Exception:
        return _decision_without_source(intent, required)

    all_sources = [
        source
        for doc, score in raw_results
        if _is_usable_source(source := _source_from_result(doc, score))
    ]
    matched_sources = [
        source for source in all_sources if source.content_type in required
    ][:k]
    selected_sources = matched_sources or all_sources[:k]
    quality = judge_retrieval_quality(
        selected_sources,
        intent=intent,
        required_content_types=required,
        knowledge_points=knowledge_points,
    )
    if quality in {QUALITY_NONE, QUALITY_LOW}:
        selected_sources = []

    context_text = "\n\n".join(
        f"【{source.title}】\n"
        f"content_type={source.content_type}; section_type={source.section_type}; "
        f"source={source.source}\n{source.text}"
        for source in selected_sources
    )
    return RetrievalDecision(
        answer_mode=_answer_mode_for_quality(intent, quality),
        retrieval_quality=quality,
        required_content_types=required,
        sources=selected_sources,
        context_text=context_text,
    )
