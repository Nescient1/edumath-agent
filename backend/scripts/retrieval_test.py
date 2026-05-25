import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import VECTOR_STORE_DIR
from app.services.embedding_service import ensure_compatible_vector_store, resolve_embeddings
from pipeline_utils import read_json


DEFAULT_QUERY = "我只会求导但不会判断单调区间"
PASS_KEYWORDS = ["导数与函数单调性", "函数的单调性", "单调区间", "f'(x)>0", "f'(x)<0"]
VECTOR_DB_DIR = VECTOR_STORE_DIR
LOCAL_INDEX_PATH = VECTOR_DB_DIR.parent / "local_vector_index.json"


class LocalDoc:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def run_local_json_retrieval(query: str, k: int) -> list[tuple[object, float]]:
    index = read_json(LOCAL_INDEX_PATH, {})
    entries = index.get("entries", [])
    if not entries:
        raise RuntimeError(f"Local vector index is empty or missing at {LOCAL_INDEX_PATH}.")

    embeddings, embedding_config = resolve_embeddings()
    existing_config = index.get("embedding", {})
    comparable_keys = ["provider", "model", "dimension"]
    existing = {key: existing_config.get(key) for key in comparable_keys}
    current = {key: embedding_config.get(key) for key in comparable_keys}
    if existing != current:
        raise RuntimeError(
            "Embedding configuration does not match the local JSON vector index. "
            f"Existing={existing}, Current={current}. "
            f"Delete {LOCAL_INDEX_PATH} and rerun scripts/embed_to_chroma.py."
        )

    query_embedding = embeddings.embed_query(query)
    scored = []
    for entry in entries:
        score = cosine_similarity(query_embedding, entry["embedding"])
        scored.append((LocalDoc(entry["text"], entry["metadata"]), score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:k]


def run_retrieval_test(query: str = DEFAULT_QUERY, k: int = 5) -> list[tuple[object, float]]:
    if LOCAL_INDEX_PATH.exists() and not VECTOR_DB_DIR.exists():
        return run_local_json_retrieval(query, k)

    if not VECTOR_DB_DIR.exists():
        raise RuntimeError(
            f"Vector DB does not exist at {VECTOR_DB_DIR} and local index does not exist at {LOCAL_INDEX_PATH}. "
            "Run scripts/embed_postgres_to_chroma.py first."
        )

    try:
        from langchain_chroma import Chroma
    except ImportError:
        if LOCAL_INDEX_PATH.exists():
            return run_local_json_retrieval(query, k)
        raise RuntimeError("Missing dependency: langchain-chroma")

    embeddings, embedding_config = resolve_embeddings()
    ensure_compatible_vector_store(embedding_config, VECTOR_DB_DIR)
    vector_store = Chroma(
        persist_directory=str(VECTOR_DB_DIR),
        embedding_function=embeddings,
    )
    return vector_store.similarity_search_with_score(query, k=k)


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    results = run_retrieval_test(query, k=5)
    print(f"Query: {query}")
    print(f"Vector DB: {VECTOR_DB_DIR}")

    joined_text = ""
    for index, (doc, score) in enumerate(results, start=1):
        metadata = doc.metadata or {}
        text = doc.page_content.strip()
        joined_text += "\n" + text
        print(f"\n[{index}] score: {score}")
        print(f"source: {metadata.get('source')}")
        print(f"content_type: {metadata.get('content_type')}")
        print(f"section_type: {metadata.get('section_type')}")
        print(f"knowledge_points: {metadata.get('knowledge_points')}")
        print("text:")
        print(text[:700])

    if any(keyword in joined_text for keyword in PASS_KEYWORDS):
        print("\nPASS: derivative monotonicity related content was retrieved.")
    else:
        print("\nWARNING: derivative monotonicity content was not found in top results.")


if __name__ == "__main__":
    main()
