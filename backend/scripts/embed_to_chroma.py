import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.embedding_service import LocalHashEmbeddings, ensure_compatible_vector_store, resolve_embeddings, write_embedding_config
from pipeline_utils import CHUNKS_DIR, VECTOR_DB_DIR, ensure_pipeline_dirs, read_json, relative_to_backend, write_json


LOCAL_INDEX_PATH = VECTOR_DB_DIR.parent / "local_vector_index.json"


def _chunk_metadata(chunk: dict) -> dict:
    return {
        "chunk_id": chunk["chunk_id"],
        "source": chunk["source"],
        "source_path": chunk["source_path"],
        "content_type": chunk["content_type"],
        "section_type": chunk["section_type"],
        "knowledge_points": ",".join(chunk.get("knowledge_points", [])),
        "char_count": chunk["char_count"],
    }


def embed_chunks_to_local_json(chunks: list[dict]) -> None:
    embeddings = LocalHashEmbeddings()
    entries = []
    for chunk in chunks:
        entries.append(
            {
                "id": chunk["chunk_id"],
                "text": chunk["text"],
                "metadata": _chunk_metadata(chunk),
                "embedding": embeddings.embed_query(chunk["text"]),
            }
        )

    config = {
        "provider": "local-json-hash",
        "model": "local-hash-v1",
        "dimension": embeddings.dimension,
    }
    write_json(
        LOCAL_INDEX_PATH,
        {
            "embedding": config,
            "entries": entries,
        },
    )
    write_json(
        VECTOR_DB_DIR.parent / "embed_manifest.json",
        {
            "input": relative_to_backend(CHUNKS_DIR / "chunks.json"),
            "output": relative_to_backend(LOCAL_INDEX_PATH),
            "chunk_count": len(chunks),
            "embedding": config,
            "fallback_reason": "langchain-chroma is not installed",
        },
    )
    print("langchain-chroma is not installed; wrote local JSON vector index instead.")
    print(f"Output: {LOCAL_INDEX_PATH}")
    print(f"Embedded chunks: {len(chunks)}")


def embed_chunks_to_chroma() -> None:
    chunks_path = CHUNKS_DIR / "chunks.json"
    chunks = read_json(chunks_path, [])
    if not chunks:
        raise RuntimeError(f"No chunks found at {chunks_path}.")

    try:
        from langchain_chroma import Chroma
    except ImportError:
        embed_chunks_to_local_json(chunks)
        return

    embeddings, embedding_config = resolve_embeddings()
    print(
        "Using embedding provider: "
        f"{embedding_config['provider']} ({embedding_config['model']})"
    )
    ensure_compatible_vector_store(embedding_config, VECTOR_DB_DIR)

    texts = [chunk["text"] for chunk in chunks]
    metadatas = [_chunk_metadata(chunk) for chunk in chunks]
    ids = [chunk["chunk_id"] for chunk in chunks]

    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    vector_store = Chroma(
        persist_directory=str(VECTOR_DB_DIR),
        embedding_function=embeddings,
    )
    vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    write_embedding_config(embedding_config, VECTOR_DB_DIR)
    write_json(
        VECTOR_DB_DIR.parent / "embed_manifest.json",
        {
            "input": relative_to_backend(chunks_path),
            "output": relative_to_backend(VECTOR_DB_DIR),
            "chunk_count": len(chunks),
            "embedding": embedding_config,
        },
    )
    print(f"Input: {chunks_path}")
    print(f"Output: {VECTOR_DB_DIR}")
    print(f"Embedded chunks: {len(chunks)}")


def main() -> None:
    ensure_pipeline_dirs()
    embed_chunks_to_chroma()


if __name__ == "__main__":
    main()
