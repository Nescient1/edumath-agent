from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

BACKEND_DIR = PROJECT_ROOT / "backend"
PIPELINE_DATA_DIR = BACKEND_DIR / "data"
PIPELINE_RAW_DIR = PIPELINE_DATA_DIR / "raw"
PIPELINE_EXTRACTED_DIR = PIPELINE_DATA_DIR / "extracted"
PIPELINE_CLEANED_DIR = PIPELINE_DATA_DIR / "cleaned"
PIPELINE_SELECTED_DIR = PIPELINE_DATA_DIR / "selected"
PIPELINE_CHUNKS_DIR = PIPELINE_DATA_DIR / "chunks"
PIPELINE_VECTOR_DB_DIR = PIPELINE_DATA_DIR / "vector_db" / "chroma"
STORAGE_DIR = BACKEND_DIR / "storage"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
VECTOR_STORE_DIR = PROJECT_ROOT / "vector_store" / "chroma"


class Settings:
    app_name = "EduMath Agent API"
    version = "0.1.0"
    api_prefix = "/api"
    cors_origins = os.getenv("CORS_ORIGINS", "*")
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_base_url = os.getenv("OPENAI_BASE_URL", "")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
    llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    enable_llm_diagnose = os.getenv("ENABLE_LLM_DIAGNOSE", "1")
    enable_llm_ocr_vision = os.getenv("ENABLE_LLM_OCR_VISION", "0")
    enable_llm_ocr_rewrite = os.getenv("ENABLE_LLM_OCR_REWRITE", "0")
    enable_llm_data_labeling = os.getenv("ENABLE_LLM_DATA_LABELING", "0")
    enable_llm_profile_advice = os.getenv("ENABLE_LLM_PROFILE_ADVICE", "1")
    enable_llm_question_generation = os.getenv("ENABLE_LLM_QUESTION_GENERATION", "0")
    enable_llm_learning_path = os.getenv("ENABLE_LLM_LEARNING_PATH", "0")
    enable_pix2text_ocr = os.getenv("ENABLE_PIX2TEXT_OCR", "0")
    pix2text_device = os.getenv("PIX2TEXT_DEVICE", "")
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    enable_openai_embedding = os.getenv("ENABLE_OPENAI_EMBEDDING", "0")
    local_embedding_model = os.getenv(
        "LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"
    )
    local_embedding_device = os.getenv("LOCAL_EMBEDDING_DEVICE", "")
    local_embedding_local_files_only = os.getenv(
        "LOCAL_EMBEDDING_LOCAL_FILES_ONLY", "1"
    )


settings = Settings()
