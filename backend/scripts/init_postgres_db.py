import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
SCHEMA_PATH = BACKEND_DIR / "sql" / "postgres_schema.sql"


def _require_psycopg():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: psycopg. Install with `pip install psycopg[binary]`."
        ) from exc
    return psycopg


def _connection_kwargs(database: str) -> dict[str, object]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": database,
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }


def _target_database(default: str = "edumath_agent") -> str:
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        parsed = urlparse(database_url)
        if parsed.path and parsed.path != "/":
            return parsed.path.lstrip("/")
    return os.getenv("POSTGRES_DB", default)


def create_database_if_missing(database: str, maintenance_db: str = "postgres") -> None:
    psycopg = _require_psycopg()
    with psycopg.connect(**_connection_kwargs(maintenance_db), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"Database already exists: {database}")
                return
            cur.execute(f'CREATE DATABASE "{database}"')
            print(f"Created database: {database}")


def apply_schema(database: str) -> None:
    psycopg = _require_psycopg()
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(**_connection_kwargs(database), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN (
                    'documents',
                    'extraction_runs',
                    'text_blocks',
                    'question_items',
                    'rag_chunks',
                    'llm_processing_runs',
                    'processing_logs',
                    'students',
                    'student_profiles',
                    'student_wrong_records',
                    'student_practice_attempts',
                    'student_practice_events'
                  )
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
    print(f"Schema applied to database: {database}")
    print("Tables:", ", ".join(tables))


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize EduMath PostgreSQL DB.")
    parser.add_argument("--database", default=None, help="Target database name.")
    parser.add_argument(
        "--maintenance-db",
        default=os.getenv("POSTGRES_MAINTENANCE_DB", "postgres"),
        help="Database used to create the target database.",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    database = args.database or _target_database()
    create_database_if_missing(database, maintenance_db=args.maintenance_db)
    apply_schema(database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
