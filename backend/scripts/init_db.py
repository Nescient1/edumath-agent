import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.database import ensure_storage


if __name__ == "__main__":
    ensure_storage()
    print("Storage directory is ready.")
