import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.llm_service import is_enabled_flag, is_llm_enabled, safe_generate_text
from pipeline_utils import CHUNKS_DIR, read_json, write_json


OUTPUT_PATH = CHUNKS_DIR / "llm_labeled_samples.json"


def _extract_json_object(text: str | None) -> dict:
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def label_sample_chunks(sample_size: int = 5) -> list[dict]:
    if not is_enabled_flag(settings.enable_llm_data_labeling):
        print("ENABLE_LLM_DATA_LABELING is disabled; no LLM labeling was run.")
        return []
    if not is_llm_enabled():
        print("LLM is not configured; no LLM labeling was run.")
        return []

    chunks_path = CHUNKS_DIR / "chunks.json"
    chunks = read_json(chunks_path, [])
    if not chunks:
        raise RuntimeError(f"No chunks found at {chunks_path}.")

    labeled = []
    for chunk in chunks[:sample_size]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是高中数学资料标注助手。请只输出 JSON，字段包括 "
                    "knowledge_points, content_type, section_type, difficulty, reason。"
                    "不要编造文本中没有的知识点。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source": chunk.get("source"),
                        "text": chunk.get("text", "")[:1800],
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        content = safe_generate_text(
            messages=messages,
            max_tokens=512,
            temperature=0.0,
            fallback=None,
        )
        labeled.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source": chunk.get("source"),
                "original_metadata": {
                    "knowledge_points": chunk.get("knowledge_points", []),
                    "content_type": chunk.get("content_type"),
                    "section_type": chunk.get("section_type"),
                },
                "llm_label": _extract_json_object(content),
            }
        )

    write_json(OUTPUT_PATH, labeled)
    print(f"Wrote {len(labeled)} labeled samples to {OUTPUT_PATH}")
    return labeled


def main() -> None:
    sample_size = 5
    if len(sys.argv) > 1:
        sample_size = int(sys.argv[1])
    label_sample_chunks(sample_size)


if __name__ == "__main__":
    main()
