from pathlib import Path

from pipeline_utils import (
    EXTRACTED_DIR,
    RAW_DIR,
    SUPPORTED_EXTENSIONS,
    ensure_pipeline_dirs,
    read_text,
    relative_to_backend,
    safe_output_stem,
    write_json,
    write_text,
)


def extract_txt(path: Path) -> str:
    return read_text(path)


def extract_markdown(path: Path) -> str:
    return read_text(path)


def extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pypdf") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(f"[[page={index}]]\n{page_text.strip()}")
    return "\n\n".join(pages)


def extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Missing dependency: python-docx") from exc

    document = Document(str(path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            style_name = paragraph.style.name if paragraph.style else ""
            if "Heading" in style_name or "标题" in style_name:
                lines.append(f"\n# {text}")
            else:
                lines.append(text)
    return "\n".join(lines)


def extract_doc(path: Path) -> str:
    raise RuntimeError(
        "Legacy .doc files are not supported in the first pipeline version. "
        "Convert to .docx or .pdf before extraction."
    )


def extract_html(path: Path) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("Missing dependency: beautifulsoup4") from exc

    soup = BeautifulSoup(read_text(path), "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        heading.string = f"\n# {heading.get_text(' ', strip=True)}\n"

    return soup.get_text("\n", strip=True)


EXTRACTORS = {
    ".txt": extract_txt,
    ".md": extract_markdown,
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".doc": extract_doc,
    ".html": extract_html,
    ".htm": extract_html,
}


def extract_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    output_path = EXTRACTED_DIR / f"{safe_output_stem(path)}.txt"
    record = {
        "source": path.name,
        "source_path": relative_to_backend(path),
        "file_type": suffix,
        "output_path": relative_to_backend(output_path),
        "status": "pending",
        "error": None,
        "text_length": 0,
    }

    if suffix not in SUPPORTED_EXTENSIONS:
        record["status"] = "skipped"
        record["error"] = f"Unsupported file type: {suffix}"
        return record

    try:
        text = EXTRACTORS[suffix](path)
        write_text(output_path, text)
        record["status"] = "success"
        record["text_length"] = len(text)
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)

    return record


def main() -> None:
    ensure_pipeline_dirs()
    files = [path for path in RAW_DIR.rglob("*") if path.is_file()]
    manifest = [extract_file(path) for path in files]
    write_json(EXTRACTED_DIR / "manifest.json", manifest)

    success = sum(1 for item in manifest if item["status"] == "success")
    skipped = sum(1 for item in manifest if item["status"] == "skipped")
    failed = sum(1 for item in manifest if item["status"] == "failed")
    print(f"Input: {RAW_DIR}")
    print(f"Output: {EXTRACTED_DIR}")
    print(f"Extracted: success={success}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
