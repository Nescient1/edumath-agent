import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

from build_chunks import build_chunks_from_items
from classify_chunks import should_keep_item
from clean_text import clean_text
from extract_text import extract_markdown, extract_txt
import retrieval_test


def test_extract_txt(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("函数与导数", encoding="utf-8")

    assert extract_txt(path) == "函数与导数"


def test_extract_markdown(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("# 导数\n\n## 单调性", encoding="utf-8")

    assert "# 导数" in extract_markdown(path)


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
