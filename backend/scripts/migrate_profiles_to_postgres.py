import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import PROJECT_ROOT
from app.repositories.profile_repository import migrate_json_profiles_to_postgres


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    result = migrate_json_profiles_to_postgres()
    print(
        "profile_migration "
        f"db_available={result['db_available']} "
        f"profiles={result['profiles']} "
        f"records={result['records']}"
    )
    return 0 if result["db_available"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
