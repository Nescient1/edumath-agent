CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT,
    subject TEXT DEFAULT '高中数学',
    topic TEXT,
    source_category TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_path, file_hash)
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extractor_type TEXT NOT NULL,
    extractor_version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    formula_count INTEGER NOT NULL DEFAULT 0,
    image_count INTEGER NOT NULL DEFAULT 0,
    quality_score NUMERIC(5, 2),
    quality_label TEXT,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS text_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    extraction_run_id UUID REFERENCES extraction_runs(id) ON DELETE SET NULL,
    block_index INTEGER NOT NULL,
    block_type TEXT NOT NULL DEFAULT 'paragraph',
    raw_text TEXT NOT NULL,
    cleaned_text TEXT,
    llm_rewritten_text TEXT,
    quality_label TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, extraction_run_id, block_index)
);

CREATE TABLE IF NOT EXISTS question_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    text_block_id UUID REFERENCES text_blocks(id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    options JSONB NOT NULL DEFAULT '[]'::jsonb,
    answer TEXT,
    solution TEXT,
    knowledge_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    difficulty TEXT,
    question_type TEXT,
    quality_label TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    question_item_id UUID REFERENCES question_items(id) ON DELETE SET NULL,
    text_block_id UUID REFERENCES text_blocks(id) ON DELETE SET NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL,
    content_type TEXT NOT NULL,
    section_type TEXT,
    knowledge_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    token_count INTEGER NOT NULL DEFAULT 0,
    vector_store TEXT,
    vector_id TEXT,
    quality_label TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS llm_processing_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    text_block_id UUID REFERENCES text_blocks(id) ON DELETE SET NULL,
    stage TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    input_tokens INTEGER,
    output_tokens INTEGER,
    error_message TEXT,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    stage TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS students (
    id TEXT PRIMARY KEY,
    name TEXT,
    grade TEXT NOT NULL DEFAULT '高三',
    target_score INTEGER NOT NULL DEFAULT 120,
    current_score INTEGER,
    textbook_version TEXT,
    current_topic TEXT,
    learning_goal TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS student_profiles (
    student_id TEXT PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
    weak_points JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_types JSONB NOT NULL DEFAULT '{}'::jsonb,
    mastery JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_wrong_questions INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS student_wrong_records (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    student_answer TEXT,
    knowledge_points JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_type TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT '未复习',
    is_mastered BOOLEAN NOT NULL DEFAULT false,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_source_category ON documents(source_category);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_document_id ON extraction_runs(document_id);
CREATE INDEX IF NOT EXISTS idx_text_blocks_document_id ON text_blocks(document_id);
CREATE INDEX IF NOT EXISTS idx_question_items_document_id ON question_items(document_id);
CREATE INDEX IF NOT EXISTS idx_question_items_quality_label ON question_items(quality_label);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_content_type ON rag_chunks(content_type);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_quality_label ON rag_chunks(quality_label);
CREATE INDEX IF NOT EXISTS idx_processing_logs_document_id ON processing_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_student_wrong_records_student_id ON student_wrong_records(student_id);
CREATE INDEX IF NOT EXISTS idx_student_wrong_records_created_at ON student_wrong_records(created_at);

CREATE TABLE IF NOT EXISTS student_practice_attempts (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    student_input TEXT,
    ocr_image_path TEXT,
    recognized_answer TEXT,
    score INTEGER,
    is_correct BOOLEAN,
    feedback TEXT,
    assist_mode TEXT NOT NULL DEFAULT 'grade',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS student_practice_events (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    attempt_id TEXT REFERENCES student_practice_attempts(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_student_practice_attempts_student_id ON student_practice_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_student_practice_attempts_question_id ON student_practice_attempts(question_id);
CREATE INDEX IF NOT EXISTS idx_student_practice_events_student_id ON student_practice_events(student_id);
CREATE INDEX IF NOT EXISTS idx_student_practice_events_question_id ON student_practice_events(question_id);
