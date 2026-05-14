from app.core.config import STORAGE_DIR


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
