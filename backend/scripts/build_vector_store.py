import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import PROCESSED_DATA_DIR, VECTOR_STORE_DIR
from app.services.embedding_service import (
    ensure_compatible_vector_store,
    resolve_embeddings,
    write_embedding_config,
)


def _extract_frontmatter_metadata(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    metadata: dict[str, str] = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1].replace(",", "，")
        metadata[key] = value

    return metadata


def build_vector_store() -> None:
    try:
        from langchain_chroma import Chroma
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "Install LangChain and Chroma dependencies from requirements.txt first."
        ) from exc

    embeddings, embedding_config = resolve_embeddings()
    print(
        "Using embedding provider: "
        f"{embedding_config['provider']} ({embedding_config['model']})"
    )
    ensure_compatible_vector_store(embedding_config)

    loader = DirectoryLoader(
        str(PROCESSED_DATA_DIR),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        recursive=True,
    )
    docs = loader.load()
    if not docs:
        raise RuntimeError(f"No markdown documents found in {PROCESSED_DATA_DIR}.")

    for doc in docs:
        source_path = Path(doc.metadata.get("source", ""))
        frontmatter = _extract_frontmatter_metadata(doc.page_content)
        doc.metadata["source_path"] = str(source_path)
        doc.metadata["source_type"] = (
            source_path.parent.name if source_path.parent.name else "processed"
        )
        doc.metadata["doc_type"] = frontmatter.get("type", "")
        doc.metadata["title"] = frontmatter.get("title", source_path.stem)
        doc.metadata["knowledge_points"] = frontmatter.get("knowledge_points", "")
        doc.metadata["difficulty"] = frontmatter.get("difficulty", "")
        doc.metadata["data_source"] = frontmatter.get("source", "")

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)
    chunks = splitter.split_documents(docs)

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(VECTOR_STORE_DIR),
    )
    write_embedding_config(embedding_config)

    print(f"Vector store built at {Path(VECTOR_STORE_DIR)} with {len(chunks)} chunks.")
    print(f"Embedding config written to {VECTOR_STORE_DIR / 'embedding_config.json'}.")


if __name__ == "__main__":
    build_vector_store()
