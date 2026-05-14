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
DATA_DIR = PROJECT_ROOT / "data"
NOTES_DIR = DATA_DIR / "notes"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
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
    embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


settings = Settings()
