import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

from build_chunks import build_chunks_from_items
from classify_chunks import should_keep_item
from clean_text import clean_text
from extract_text import extract_docx_details, extract_markdown, extract_txt
import extract_text
import retrieval_test


def test_extract_txt(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("函数与导数", encoding="utf-8")

    assert extract_txt(path) == "函数与导数"


def test_extract_markdown(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("# 导数\n\n## 单调性", encoding="utf-8")

    assert "# 导数" in extract_markdown(path)


def _write_minimal_docx(path: Path, document_xml: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr("word/document.xml", document_xml)


def test_extract_docx_preserves_omml_formula(tmp_path):
    path = tmp_path / "formula.docx"
    _write_minimal_docx(
        path,
        """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    <w:p>
      <w:r><w:t>f(x)=</w:t></w:r>
      <m:oMath>
        <m:sSup>
          <m:e><m:r><m:t>x</m:t></m:r></m:e>
          <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
        </m:sSup>
      </m:oMath>
      <w:r><w:t>+1</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
""",
    )

    details = extract_docx_details(path)

    assert "f(x)=" in details.text
    assert "[FORMULA: x^2]" in details.text
    assert "+1" in details.text
    assert details.formula_count == 1


def test_extract_file_records_docx_formula_metadata(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    output_dir = tmp_path / "extracted"
    raw_dir.mkdir()
    path = raw_dir / "formula.docx"
    _write_minimal_docx(
        path,
        """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
  <w:body>
    <w:p><w:r><w:t>test</w:t></w:r><m:oMath><m:r><m:t>a</m:t></m:r></m:oMath></w:p>
  </w:body>
</w:document>
""",
    )
    monkeypatch.setattr(extract_text, "RAW_DIR", raw_dir)
    monkeypatch.setattr(extract_text, "EXTRACTED_DIR", output_dir)

    record = extract_text.extract_file(path)

    assert record["status"] == "success"
    assert record["formula_count"] == 1
    assert record["extraction_quality"] == "high"
    assert (output_dir / "formula.txt").exists()


def test_clean_text_preserves_math_options_and_solution_steps():
    raw = """
扫码关注

A. f'(x)>0
B. f'(x)<0
解：先求导，再判断单调区间。
"""

    cleaned = clean_text(raw)

    assert "扫码关注" not in cleaned
    assert "A. f'(x)>0" in cleaned
    assert "B. f'(x)<0" in cleaned
    assert "解：先求导" in cleaned


def test_clean_text_removes_short_garbled_paragraph():
    cleaned = clean_text("�#￥@\n\n导数判断函数单调性的标准步骤是先求导，再判断 f'(x) 的符号。")

    assert "�#￥@" not in cleaned
    assert "导数判断函数单调性" in cleaned


def test_should_keep_derivative_monotonicity_paragraph():
    text = "导数与函数单调性：若 f'(x)>0，则函数在该区间单调递增。"

    assert should_keep_item(text)


def test_build_chunks_generates_valid_chunks():
    items = [
        {
            "source": "导数讲义.md",
            "source_path": "data/raw/lectures/导数讲义.md",
            "content_type": "lecture_note",
            "section_type": "method",
            "knowledge_points": ["导数", "函数"],
            "text": "导数判断函数单调性的标准步骤是先求导，令 f'(x)=0，划分区间，判断导数符号，写出单调区间。"
            * 5,
        }
    ]

    chunks = build_chunks_from_items(items)

    assert chunks
    assert chunks[0]["chunk_id"] == "chunk_000001"
    assert chunks[0]["knowledge_points"] == ["导数", "函数"]


def test_retrieval_test_reports_missing_vector_store(tmp_path, monkeypatch):
    monkeypatch.setattr(retrieval_test, "VECTOR_DB_DIR", tmp_path / "missing_chroma")

    with pytest.raises(RuntimeError, match="Vector DB does not exist"):
        retrieval_test.run_retrieval_test()
