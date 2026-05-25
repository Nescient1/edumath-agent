import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

from app.core.config import VECTOR_STORE_DIR, settings


HASH_EMBEDDING_DIMENSION = 384
CONFIG_FILENAME = "embedding_config.json"
BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："


class LocalHashEmbeddings:
    """Small deterministic embedding fallback for offline demos."""

    def __init__(self, dimension: int = HASH_EMBEDDING_DIMENSION):
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = self._tokenize(text)
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        text = text.lower()
        tokens: list[str] = []
        buffer = ""
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                if buffer:
                    tokens.append(buffer)
                    buffer = ""
                tokens.append(char)
            elif char.isalnum():
                buffer += char
            else:
                if buffer:
                    tokens.append(buffer)
                    buffer = ""
        if buffer:
            tokens.append(buffer)

        bigrams = [
            tokens[index] + tokens[index + 1]
            for index in range(len(tokens) - 1)
            if len(tokens[index]) == 1 and len(tokens[index + 1]) == 1
        ]
        return tokens + bigrams


class LocalBgeEmbeddings:
    """SentenceTransformers wrapper compatible with LangChain vector stores."""

    def __init__(
        self,
        model_name: str,
        device: str = "",
        local_files_only: bool = True,
    ):
        if local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Install it or use OPENAI_API_KEY/local-hash fallback."
            ) from exc

        kwargs: dict[str, Any] = {}
        if device:
            kwargs["device"] = device
        kwargs["local_files_only"] = local_files_only
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name, **kwargs)
        except TypeError:
            kwargs.pop("local_files_only", None)
            self.model = SentenceTransformer(model_name, **kwargs)
        if hasattr(self.model, "get_embedding_dimension"):
            dimension = self.model.get_embedding_dimension()
        else:
            dimension = self.model.get_sentence_embedding_dimension()
        self.dimension = int(dimension or len(self.embed_query("测试")))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        query = f"{BGE_QUERY_INSTRUCTION}{text}"
        return self._encode([query])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vector.tolist() for vector in vectors]


def embedding_config_path(vector_store_dir: Path | None = None) -> Path:
    target_dir = vector_store_dir or VECTOR_STORE_DIR
    return target_dir / CONFIG_FILENAME


def read_embedding_config(vector_store_dir: Path | None = None) -> dict[str, Any] | None:
    path = embedding_config_path(vector_store_dir)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_embedding_config(
    config: dict[str, Any], vector_store_dir: Path | None = None
) -> None:
    target_dir = vector_store_dir or VECTOR_STORE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    with embedding_config_path(target_dir).open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def resolve_embeddings() -> tuple[Any, dict[str, Any]]:
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    base_url = settings.openai_base_url or os.getenv("OPENAI_BASE_URL", "")
    model = settings.embedding_model or os.getenv("EMBEDDING_MODEL", "")
    model = model or "text-embedding-3-small"
    enable_openai_embedding = _truthy(
        settings.enable_openai_embedding or os.getenv("ENABLE_OPENAI_EMBEDDING", "0")
    )

    if api_key and enable_openai_embedding:
        try:
            from langchain_openai import OpenAIEmbeddings

            kwargs: dict[str, Any] = {"model": model, "openai_api_key": api_key}
            if base_url:
                kwargs["openai_api_base"] = base_url

            embeddings = OpenAIEmbeddings(**kwargs)
            dimension = 1536
            if "large" in model:
                dimension = 3072
            return embeddings, {
                "provider": "openai-compatible",
                "model": model,
                "dimension": dimension,
            }
        except Exception as exc:
            print(
                "OpenAI compatible embeddings failed to initialize; "
                f"falling back to local-bge/local-hash. Reason: {exc}"
            )

    local_model = (
        settings.local_embedding_model
        or os.getenv("LOCAL_EMBEDDING_MODEL", "")
        or "BAAI/bge-small-zh-v1.5"
    )
    local_device = settings.local_embedding_device or os.getenv(
        "LOCAL_EMBEDDING_DEVICE", ""
    )
    local_files_only = _truthy(
        settings.local_embedding_local_files_only
        or os.getenv("LOCAL_EMBEDDING_LOCAL_FILES_ONLY", "1")
    )
    if local_model:
        try:
            embeddings = LocalBgeEmbeddings(
                local_model,
                device=local_device,
                local_files_only=local_files_only,
            )
            return embeddings, {
                "provider": "local-bge",
                "model": local_model,
                "dimension": embeddings.dimension,
            }
        except Exception as exc:
            print(
                "Local BGE embeddings failed to initialize; "
                f"falling back to local-hash. Reason: {exc}"
            )

    embeddings = LocalHashEmbeddings()
    return embeddings, {
        "provider": "local-hash",
        "model": "local-hash-v1",
        "dimension": HASH_EMBEDDING_DIMENSION,
    }


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_compatible_vector_store(
    current_config: dict[str, Any], vector_store_dir: Path | None = None
) -> None:
    existing_config = read_embedding_config(vector_store_dir)
    if existing_config is None:
        return

    comparable_keys = ["provider", "model", "dimension"]
    existing = {key: existing_config.get(key) for key in comparable_keys}
    current = {key: current_config.get(key) for key in comparable_keys}

    if existing != current:
        raise RuntimeError(
            "Embedding configuration does not match the existing vector store. "
            f"Existing={existing}, Current={current}. "
            f"Delete {vector_store_dir or VECTOR_STORE_DIR} and rebuild it."
        )
