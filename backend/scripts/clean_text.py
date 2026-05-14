import re

from pipeline_utils import (
    AD_KEYWORDS,
    CLEANED_DIR,
    EXTRACTED_DIR,
    backend_path,
    ensure_pipeline_dirs,
    is_probably_garbled,
    read_json,
    read_text,
    relative_to_backend,
    write_json,
    write_text,
)


PROTECTED_PATTERNS = [
    r"^[A-D][\.．、]\s*",
    r"^解[:：]",
    r"^解析[:：]",
    r"^证明[:：]",
    r"f['’]\(x\)",
    r"^\(?\d+\)?[\.、．]",
]


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines())


def remove_page_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"第?\s*\d+\s*页?", stripped):
            continue
        if re.fullmatch(r"page\s*\d+", stripped, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\[\[page=\d+\]\]", stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_protected(line: str) -> bool:
    return any(re.search(pattern, line) for pattern in PROTECTED_PATTERNS)


def remove_ad_lines(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) <= 40 and any(keyword in stripped for keyword in AD_KEYWORDS):
            continue
        cleaned.append(line)
    return cleaned


def remove_duplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    seen: set[str] = set()
    unique = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", "", paragraph)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(paragraph)
    return unique


def is_meaningful_paragraph(paragraph: str) -> bool:
    stripped = paragraph.strip()
    if not stripped:
        return False
    if _is_protected(stripped):
        return True
    if is_probably_garbled(stripped):
        return False
    if len(stripped) < 8 and not re.search(r"[=<>≤≥√∞∈]", stripped):
        return False
    return True


def clean_text(text: str) -> str:
    text = normalize_whitespace(text)
    text = remove_page_noise(text)
    lines = remove_ad_lines(text.splitlines())
    text = "\n".join(lines)
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [paragraph.strip() for paragraph in paragraphs]
    paragraphs = [paragraph for paragraph in paragraphs if is_meaningful_paragraph(paragraph)]
    paragraphs = remove_duplicate_paragraphs(paragraphs)
    return "\n\n".join(paragraphs).strip() + ("\n" if paragraphs else "")


def main() -> None:
    ensure_pipeline_dirs()
    extract_manifest = read_json(EXTRACTED_DIR / "manifest.json", [])
    manifest = []

    for item in extract_manifest:
        if item.get("status") != "success":
            continue
        input_path = backend_path(item["output_path"])
        output_path = CLEANED_DIR / input_path.name
        record = {
            "source": item["source"],
            "source_path": item["source_path"],
            "input_path": item["output_path"],
            "output_path": relative_to_backend(output_path),
            "status": "pending",
            "error": None,
            "original_length": 0,
            "cleaned_length": 0,
        }
        try:
            raw = read_text(input_path)
            cleaned = clean_text(raw)
            write_text(output_path, cleaned)
            record["status"] = "success"
            record["original_length"] = len(raw)
            record["cleaned_length"] = len(cleaned)
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
        manifest.append(record)

    write_json(CLEANED_DIR / "clean_manifest.json", manifest)
    success = sum(1 for item in manifest if item["status"] == "success")
    failed = sum(1 for item in manifest if item["status"] == "failed")
    print(f"Input: {EXTRACTED_DIR}")
    print(f"Output: {CLEANED_DIR}")
    print(f"Cleaned: success={success}, failed={failed}")


if __name__ == "__main__":
    main()
