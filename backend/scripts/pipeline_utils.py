import json
import re
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
PIPELINE_DATA_DIR = BACKEND_DIR / "data"
RAW_DIR = PIPELINE_DATA_DIR / "raw"
RAW_TEMP_DIR = PIPELINE_DATA_DIR / "raw_temp"
EXTRACTED_DIR = PIPELINE_DATA_DIR / "extracted"
CLEANED_DIR = PIPELINE_DATA_DIR / "cleaned"
SELECTED_DIR = PIPELINE_DATA_DIR / "selected"
CHUNKS_DIR = PIPELINE_DATA_DIR / "chunks"
VECTOR_DB_DIR = PIPELINE_DATA_DIR / "vector_db" / "chroma"

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".doc", ".html", ".htm"}

MATH_KEYWORDS = [
    "函数",
    "导数",
    "数列",
    "三角函数",
    "解三角形",
    "向量",
    "立体几何",
    "空间向量",
    "解析几何",
    "圆锥曲线",
    "椭圆",
    "双曲线",
    "抛物线",
    "概率",
    "统计",
    "排列组合",
    "不等式",
    "复数",
    "集合",
    "逻辑",
    "单调性",
    "极值",
    "最值",
    "零点",
    "恒成立",
    "证明",
    "解析",
    "例题",
    "方法",
    "公式",
    "定理",
]

AD_KEYWORDS = [
    "下载地址",
    "扫码关注",
    "微信公众号",
    "版权归原作者",
    "仅供学习交流",
    "联系客服",
    "加入qq群",
    "加入QQ群",
    "免费资料",
    "更多资料",
]


def ensure_pipeline_dirs() -> None:
    for path in [
        RAW_DIR,
        EXTRACTED_DIR,
        CLEANED_DIR,
        SELECTED_DIR,
        CHUNKS_DIR,
        VECTOR_DB_DIR.parent,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def relative_to_backend(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BACKEND_DIR.resolve()))
    except ValueError:
        return str(path)


def backend_path(relative_path: str) -> Path:
    return BACKEND_DIR / relative_path


def safe_output_stem(source_path: Path) -> str:
    try:
        relative = source_path.relative_to(RAW_DIR)
        parts = list(relative.parts)
    except ValueError:
        parts = [source_path.name]
    parts[-1] = source_path.stem
    return "__".join(parts)


def has_math_keyword(text: str) -> bool:
    return any(keyword in text for keyword in MATH_KEYWORDS)


def is_probably_garbled(text: str) -> bool:
    if not text.strip():
        return True
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return True
    replacement_count = text.count("�")
    if replacement_count / max(len(visible), 1) > 0.05:
        return True
    useful_count = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9=+\-*/()（）{}[\]，。,.；;：:<>≤≥√∞∈']", text))
    return useful_count / max(len(visible), 1) < 0.45


def estimate_tokens(text: str) -> int:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return int(chinese_chars * 0.55 + latin_words * 1.2)
