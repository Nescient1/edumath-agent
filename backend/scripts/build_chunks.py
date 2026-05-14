import re

from pipeline_utils import (
    CHUNKS_DIR,
    ensure_pipeline_dirs,
    estimate_tokens,
    has_math_keyword,
    is_probably_garbled,
    read_json,
    relative_to_backend,
    write_json,
)


MIN_CHARS = 80
TARGET_CHARS = 780
OVERLAP_CHARS = 120


def _is_short_but_valid(text: str) -> bool:
    return bool(re.search(r"定义|定理|公式|结论|[=<>≤≥√∞∈]", text))


def is_valid_chunk(text: str) -> bool:
    stripped = text.strip()
    if is_probably_garbled(stripped):
        return False
    if len(stripped) < MIN_CHARS and not _is_short_but_valid(stripped):
        return False
    return has_math_keyword(stripped)


def split_text_to_chunks(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= TARGET_CHARS:
        return [text] if text else []

    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(current) + len(paragraph) + 2 <= TARGET_CHARS:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= TARGET_CHARS:
            current = paragraph
        else:
            start = 0
            while start < len(paragraph):
                end = start + TARGET_CHARS
                chunks.append(paragraph[start:end].strip())
                start = max(end - OVERLAP_CHARS, start + 1)
            current = ""

    if current:
        chunks.append(current)

    return chunks


def build_chunks_from_items(items: list[dict]) -> list[dict]:
    chunks: list[dict] = []
    for item in items:
        for text in split_text_to_chunks(item["text"]):
            if not is_valid_chunk(text):
                continue
            chunks.append(
                {
                    "chunk_id": f"chunk_{len(chunks) + 1:06d}",
                    "source": item["source"],
                    "source_path": item["source_path"],
                    "content_type": item["content_type"],
                    "section_type": item["section_type"],
                    "knowledge_points": item["knowledge_points"],
                    "text": text,
                    "char_count": len(text),
                    "token_estimate": estimate_tokens(text),
                }
            )
    return chunks


def main() -> None:
    ensure_pipeline_dirs()
    selected_path = CHUNKS_DIR.parent / "selected" / "selected_items.json"
    items = read_json(selected_path, [])
    if not items:
        raise RuntimeError(f"No selected items found at {selected_path}.")

    chunks = build_chunks_from_items(items)
    if not chunks:
        raise RuntimeError("No valid chunks were generated.")

    output_path = CHUNKS_DIR / "chunks.json"
    write_json(output_path, chunks)
    write_json(
        CHUNKS_DIR / "chunks_manifest.json",
        {
            "input": relative_to_backend(selected_path),
            "output": relative_to_backend(output_path),
            "selected_count": len(items),
            "chunk_count": len(chunks),
        },
    )
    print(f"Input: {selected_path}")
    print(f"Output: {output_path}")
    print(f"Chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
