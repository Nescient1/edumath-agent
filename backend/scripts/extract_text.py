from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

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


NAMESPACES = {
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


@dataclass
class ExtractionDetails:
    text: str
    formula_count: int = 0
    image_count: int = 0
    warnings: list[str] = field(default_factory=list)


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


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _math_attr(node: ET.Element, name: str) -> str:
    return node.attrib.get(f"{{{NAMESPACES['m']}}}{name}", "")


def _math_text(node: ET.Element | None) -> str:
    if node is None:
        return ""

    name = _local_name(node.tag)
    if name == "t":
        return node.text or ""
    if name in {"num", "den", "e", "sub", "sup", "deg", "fName"}:
        return "".join(_math_text(child) for child in node)
    if name == "f":
        numerator = node.find("m:num", NAMESPACES)
        denominator = node.find("m:den", NAMESPACES)
        return f"({_math_text(numerator)})/({_math_text(denominator)})"
    if name == "rad":
        degree = _math_text(node.find("m:deg", NAMESPACES))
        expression = _math_text(node.find("m:e", NAMESPACES))
        return f"root[{degree}]({expression})" if degree else f"sqrt({expression})"
    if name == "sSub":
        return f"{_math_text(node.find('m:e', NAMESPACES))}_{_math_text(node.find('m:sub', NAMESPACES))}"
    if name == "sSup":
        return f"{_math_text(node.find('m:e', NAMESPACES))}^{_math_text(node.find('m:sup', NAMESPACES))}"
    if name == "sSubSup":
        return (
            f"{_math_text(node.find('m:e', NAMESPACES))}_"
            f"{_math_text(node.find('m:sub', NAMESPACES))}^"
            f"{_math_text(node.find('m:sup', NAMESPACES))}"
        )
    if name == "func":
        function_name = _math_text(node.find("m:fName", NAMESPACES))
        expression = _math_text(node.find("m:e", NAMESPACES))
        return f"{function_name}({expression})"
    if name == "nary":
        chr_node = node.find("m:naryPr/m:chr", NAMESPACES)
        operator = _math_attr(chr_node, "val") if chr_node is not None else ""
        sub = _math_text(node.find("m:sub", NAMESPACES))
        sup = _math_text(node.find("m:sup", NAMESPACES))
        expression = _math_text(node.find("m:e", NAMESPACES))
        bounds = f"_{sub}" if sub else ""
        bounds += f"^{sup}" if sup else ""
        return f"{operator}{bounds}({expression})"
    if name in {"d", "bar", "acc", "groupChr", "limLow", "limUpp"}:
        expression = node.find("m:e", NAMESPACES)
        if expression is not None:
            return _math_text(expression)

    return "".join(_math_text(child) for child in node)


def _format_formula(node: ET.Element) -> str:
    text = " ".join(_math_text(node).split())
    return f"[FORMULA: {text or 'unrecognized'}]"


def _paragraph_style(paragraph: ET.Element) -> str:
    style = paragraph.find("./w:pPr/w:pStyle", NAMESPACES)
    if style is None:
        return ""
    return style.attrib.get(f"{{{NAMESPACES['w']}}}val", "")


def _is_heading_style(style: str) -> bool:
    lowered = style.lower()
    return lowered.startswith("heading") or lowered in {"1", "2", "3"}


def _run_text(run: ET.Element) -> tuple[str, int, int]:
    parts: list[str] = []
    formula_count = 0
    image_count = 0

    for child in run:
        name = _local_name(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "tab":
            parts.append("\t")
        elif name in {"br", "cr"}:
            parts.append("\n")
        elif name in {"drawing", "pict"}:
            parts.append("[IMAGE_OR_IMAGE_FORMULA]")
            image_count += 1

    return "".join(parts), formula_count, image_count


def _paragraph_text(paragraph: ET.Element) -> tuple[str, int, int]:
    parts: list[str] = []
    formula_count = 0
    image_count = 0

    for child in paragraph:
        name = _local_name(child.tag)
        if name == "r":
            text, formulas, images = _run_text(child)
            parts.append(text)
            formula_count += formulas
            image_count += images
        elif name in {"oMath", "oMathPara"}:
            parts.append(_format_formula(child))
            formula_count += 1
        elif name == "hyperlink":
            for run in child.findall(".//w:r", NAMESPACES):
                text, formulas, images = _run_text(run)
                parts.append(text)
                formula_count += formulas
                image_count += images

    text = "".join(parts).strip()
    return text, formula_count, image_count


def _table_text(table: ET.Element) -> tuple[list[str], int, int]:
    lines: list[str] = []
    formula_count = 0
    image_count = 0

    for row in table.findall("./w:tr", NAMESPACES):
        cells = []
        for cell in row.findall("./w:tc", NAMESPACES):
            cell_parts = []
            for paragraph in cell.findall("./w:p", NAMESPACES):
                text, formulas, images = _paragraph_text(paragraph)
                formula_count += formulas
                image_count += images
                if text:
                    cell_parts.append(text)
            cells.append(" ".join(cell_parts))
        if any(cell.strip() for cell in cells):
            lines.append(" | ".join(cells))

    return lines, formula_count, image_count


def _docx_xml_details(path: Path) -> ExtractionDetails:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")
        media_count = len(
            [
                name
                for name in archive.namelist()
                if name.startswith("word/media/") and not name.endswith("/")
            ]
        )

    root = ET.fromstring(document_xml)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        return ExtractionDetails(
            text="",
            image_count=media_count,
            warnings=["missing word/document.xml body"],
        )

    lines: list[str] = []
    formula_count = 0
    inline_image_count = 0

    for child in body:
        name = _local_name(child.tag)
        if name == "p":
            text, formulas, images = _paragraph_text(child)
            formula_count += formulas
            inline_image_count += images
            if not text:
                continue
            if _is_heading_style(_paragraph_style(child)):
                lines.append(f"\n# {text}")
            else:
                lines.append(text)
        elif name == "tbl":
            table_lines, formulas, images = _table_text(child)
            formula_count += formulas
            inline_image_count += images
            lines.extend(table_lines)

    image_count = max(media_count, inline_image_count)
    warnings: list[str] = []
    if image_count:
        warnings.append(
            f"docx contains {image_count} image(s); image formulas may need OCR"
        )

    return ExtractionDetails(
        text="\n".join(line for line in lines if line.strip()),
        formula_count=formula_count,
        image_count=image_count,
        warnings=warnings,
    )


def extract_docx_details(path: Path) -> ExtractionDetails:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError("Missing dependency: python-docx") from exc

    try:
        details = _docx_xml_details(path)
        if details.text.strip():
            return details
    except Exception as exc:
        details = ExtractionDetails(text="", warnings=[f"xml_parse_failed: {exc}"])

    document = Document(str(path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style else ""
        if "Heading" in style_name:
            lines.append(f"\n# {text}")
        else:
            lines.append(text)

    details.text = "\n".join(lines)
    details.warnings.append("fallback_python_docx_text_only")
    return details


def extract_docx(path: Path) -> str:
    return extract_docx_details(path).text


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


def _quality_for_record(record: dict) -> str:
    if record["status"] == "failed":
        return "failed"
    if record["file_type"] == ".docx" and record["warnings"]:
        return "medium"
    if record["image_count"] and not record["formula_count"]:
        return "medium"
    return "high"


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
        "formula_count": 0,
        "image_count": 0,
        "extraction_quality": "unknown",
        "warnings": [],
    }

    if suffix not in SUPPORTED_EXTENSIONS:
        record["status"] = "skipped"
        record["error"] = f"Unsupported file type: {suffix}"
        record["extraction_quality"] = "skipped"
        return record

    try:
        if suffix == ".docx":
            details = extract_docx_details(path)
            text = details.text
            record["formula_count"] = details.formula_count
            record["image_count"] = details.image_count
            record["warnings"] = details.warnings
        else:
            text = EXTRACTORS[suffix](path)

        write_text(output_path, text)
        record["status"] = "success"
        record["text_length"] = len(text)
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = str(exc)

    record["extraction_quality"] = _quality_for_record(record)
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
