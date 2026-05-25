import os

from app.core.config import STORAGE_DIR


def ensure_storage() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Create PostgreSQL tables if they don't exist. No-op if PG is unavailable."""
    try:
        import psycopg

        conn = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            connect_timeout=3,
        )
    except Exception:
        return

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS students (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        grade TEXT DEFAULT '高三',
                        target_score INTEGER DEFAULT 120,
                        current_score INTEGER,
                        textbook_version TEXT DEFAULT '',
                        current_topic TEXT DEFAULT '函数与导数',
                        learning_goal TEXT DEFAULT '',
                        updated_at TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS student_profiles (
                        student_id TEXT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
                        weak_points JSONB NOT NULL DEFAULT '{}'::jsonb,
                        error_types JSONB NOT NULL DEFAULT '{}'::jsonb,
                        mastery JSONB NOT NULL DEFAULT '{}'::jsonb,
                        total_wrong_questions INTEGER NOT NULL DEFAULT 0,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        updated_at TIMESTAMPTZ DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS student_wrong_records (
                        id TEXT PRIMARY KEY,
                        student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                        question_text TEXT NOT NULL,
                        student_answer TEXT,
                        knowledge_points JSONB NOT NULL DEFAULT '[]'::jsonb,
                        error_type TEXT,
                        diagnosis TEXT,
                        review_status TEXT DEFAULT '未复习',
                        is_mastered BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_wrong_records_student
                    ON student_wrong_records(student_id)
                    """
                )
    except Exception:
        pass
    finally:
        conn.close()
