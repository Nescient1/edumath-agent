from app.services.embedding_service import LocalHashEmbeddings, resolve_embeddings
from app.services.rag_service import retrieve_context


def test_local_hash_embeddings_are_deterministic():
    embeddings = LocalHashEmbeddings()
    first = embeddings.embed_query("导数与函数单调性")
    second = embeddings.embed_query("导数与函数单调性")

    assert first == second
    assert len(first) == 384


def test_resolve_embeddings_falls_back_without_key():
    _, config = resolve_embeddings()

    assert config["provider"] in {"local-hash", "local-bge", "openai-compatible"}
    assert "dimension" in config


def test_retrieve_context_without_vector_store_is_readable():
    result = retrieve_context("我只会求导但不会判断单调区间", k=5)

    assert result
    assert isinstance(result[0], str)
