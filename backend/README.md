# EduMath Agent Backend

FastAPI backend for the MVP diagnostic loop.

## Run

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000/api`.

## Build RAG Vector Store

```bash
cd backend
python scripts\build_vector_store.py
python scripts\test_rag.py
```

The builder only reads `data/processed/**/*.md` and writes Chroma data to
`vector_store/chroma`.

Embedding behavior:

- If `OPENAI_API_KEY` is configured, the builder uses OpenAI-compatible embeddings.
- `OPENAI_BASE_URL` and `EMBEDDING_MODEL` are read from `.env` or the environment.
- Without a key, it falls back to local Hash Embedding for no-key demos.
- Formal retrieval quality should use OpenAI-compatible embeddings; local fallback is only for offline demonstration.
- If `vector_store/chroma/embedding_config.json` does not match the current provider/model/dimension, delete `vector_store/chroma` and rebuild.

## Local Data Pipeline

Put legally downloaded local materials into `backend/data/raw`, then run:

```bash
python scripts\run_data_pipeline.py
```

Single steps:

```bash
python scripts\extract_text.py
python scripts\clean_text.py
python scripts\classify_chunks.py
python scripts\build_chunks.py
python scripts\embed_to_chroma.py
python scripts\retrieval_test.py
```

Pipeline outputs:

- `backend/data/extracted`: extracted text and manifest
- `backend/data/cleaned`: cleaned text and manifest
- `backend/data/selected`: selected math items
- `backend/data/chunks`: structured chunks
- `backend/data/vector_db/chroma`: pipeline Chroma vector store

## Main Endpoints

- `GET /api/health`
- `POST /api/ocr`
- `GET /api/questions`
- `POST /api/diagnose`
- `POST /api/recommend`
- `GET /api/profile/{student_id}`
- `GET /api/profile/{student_id}/records`
- `POST /api/practice/grade`

## OCR Input

`POST /api/ocr` accepts an image file and returns:

```json
{
  "ocr_text": "recognized lines joined by newlines",
  "blocks": [
    {
      "text": "recognized line",
      "confidence": 0.98
    }
  ]
}
```

Uploads are stored temporarily under `uploads/` and removed after OCR finishes.
