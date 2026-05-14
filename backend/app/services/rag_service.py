from pathlib import Path
from typing import Any

from app.core.config import VECTOR_STORE_DIR
from app.services.embedding_service import (
    ensure_compatible_vector_store,
    read_embedding_config,
    resolve_embeddings,
)


_VECTOR_STORE: Any = None


def _vector_store_exists() -> bool:
    return VECTOR_STORE_DIR.exists() and any(VECTOR_STORE_DIR.iterdir())


def _get_vector_store() -> Any:
    global _VECTOR_STORE
    if _VECTOR_STORE is not None:
        return _VECTOR_STORE

    if not _vector_store_exists() or read_embedding_config() is None:
        return None

    try:
        from langchain_chroma import Chroma
    except ImportError:
        return None

    embeddings, embedding_config = resolve_embeddings()
    ensure_compatible_vector_store(embedding_config)
    print(
        "Using embedding provider: "
        f"{embedding_config['provider']} ({embedding_config['model']})"
    )

    _VECTOR_STORE = Chroma(
        persist_directory=str(VECTOR_STORE_DIR),
        embedding_function=embeddings,
    )
    return _VECTOR_STORE


def _format_document(doc: Any, index: int) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    source_path = metadata.get("source_path") or metadata.get("source") or "unknown"
    title = metadata.get("title") or Path(source_path).stem or f"result_{index}"
    source_type = metadata.get("source_type") or Path(source_path).parent.name
    doc_type = metadata.get("doc_type") or "unknown"
    knowledge_points = metadata.get("knowledge_points") or ""
    content = getattr(doc, "page_content", "").strip()
    if len(content) > 1000:
        content = f"{content[:1000]}..."

    return (
        f"【{title}】\n"
        f"文档类型：{doc_type}\n"
        f"来源类型：{source_type}\n"
        f"来源路径：{source_path}\n\n"
        f"知识点：{knowledge_points}\n\n"
        f"{content}"
    )


def retrieve_context(query: str, k: int = 5) -> list[str]:
    if not query.strip():
        return []

    try:
        vector_store = _get_vector_store()
    except RuntimeError as exc:
        return [f"RAG 向量库配置不一致：{exc}"]
    except Exception as exc:
        return [f"RAG 检索初始化失败：{exc}"]

    if vector_store is None:
        return [
            "RAG 向量库尚未构建。请在项目根目录运行："
            "python backend/scripts/build_vector_store.py；"
            "或在 backend 目录运行：python scripts/build_vector_store.py"
        ]

    try:
        docs = vector_store.similarity_search(query, k=k)
    except Exception as exc:
        return [f"RAG 检索失败：{exc}"]

    return [_format_document(doc, index) for index, doc in enumerate(docs, start=1)]
