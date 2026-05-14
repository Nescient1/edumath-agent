import re

from pipeline_utils import (
    CLEANED_DIR,
    SELECTED_DIR,
    backend_path,
    ensure_pipeline_dirs,
    has_math_keyword,
    is_probably_garbled,
    read_json,
    read_text,
    relative_to_backend,
    write_json,
)


KNOWLEDGE_KEYWORDS = {
    "函数": ["函数", "定义域", "值域", "单调性", "零点"],
    "导数": ["导数", "求导", "f'(x)", "f’(x)", "切线", "极值", "最值", "单调区间"],
    "数列": ["数列", "等差", "等比", "通项", "前n项和"],
    "三角函数": ["三角函数", "正弦", "余弦", "正切", "周期"],
    "解三角形": ["解三角形", "正弦定理", "余弦定理"],
    "向量": ["向量", "数量积", "空间向量"],
    "立体几何": ["立体几何", "线面", "面面", "垂直", "平行"],
    "解析几何": ["解析几何", "圆锥曲线", "椭圆", "双曲线", "抛物线"],
    "概率统计": ["概率", "统计", "随机变量", "分布列"],
    "排列组合": ["排列", "组合", "计数"],
    "不等式": ["不等式", "恒成立", "证明"],
    "复数": ["复数", "虚数", "共轭"],
    "集合逻辑": ["集合", "逻辑", "命题", "充分", "必要"],
}


def infer_content_type(source_path: str, text: str) -> str:
    normalized = source_path.replace("\\", "/")
    if "/official/" in normalized:
        return "official_standard"
    if "/lectures/" in normalized:
        return "lecture_note"
    if "/exercises/" in normalized:
        return "exercise"
    if "/exams_with_solution/" in normalized:
        return "exam_with_solution"
    if "/exams_only/" in normalized:
        return "exam_only"
    if "易错" in text:
        return "error_note"
    if "总结" in text or "知识点" in text:
        return "knowledge_summary"
    return "unknown"


def infer_section_type(text: str) -> str:
    sample = text[:120]
    if re.search(r"定义|概念|叫做|称为", sample):
        return "concept"
    if re.search(r"公式|定理|性质|结论", sample):
        return "formula"
    if re.search(r"方法|步骤|技巧|思路|规律", sample):
        return "method"
    if re.search(r"例题|例\d+|典型例题", sample):
        return "example"
    if re.search(r"题目|已知|求|证明|选择题|填空题", sample):
        return "question"
    if re.search(r"解析[:：]|解[:：]|答案[:：]|证明[:：]", sample):
        return "solution"
    if re.search(r"易错|错误|误区|注意", sample):
        return "common_mistake"
    if re.search(r"总结|小结|归纳", sample):
        return "summary"
    return "other"


def infer_knowledge_points(text: str) -> list[str]:
    points = []
    for point, keywords in KNOWLEDGE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            points.append(point)
    return points[:5]


def split_candidate_items(text: str) -> list[str]:
    sections = re.split(r"\n\s*\n", text)
    items: list[str] = []
    buffer = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(buffer) + len(section) < 900:
            buffer = f"{buffer}\n\n{section}".strip()
        else:
            if buffer:
                items.append(buffer)
            buffer = section
    if buffer:
        items.append(buffer)
    return items


def should_keep_item(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 20:
        return False
    if is_probably_garbled(stripped):
        return False
    if re.fullmatch(r"(答案|参考答案)[:：]?\s*[A-D0-9，,、\s]+", stripped):
        return False
    return has_math_keyword(stripped)


def build_selected_items() -> list[dict]:
    clean_manifest = read_json(CLEANED_DIR / "clean_manifest.json", [])
    selected: list[dict] = []

    for item in clean_manifest:
        if item.get("status") != "success":
            continue
        cleaned_path = backend_path(item["output_path"])
        text = read_text(cleaned_path)
        for candidate in split_candidate_items(text):
            if not should_keep_item(candidate):
                continue
            selected.append(
                {
                    "id": f"selected_{len(selected) + 1:06d}",
                    "source": item["source"],
                    "source_path": item["source_path"],
                    "cleaned_path": relative_to_backend(cleaned_path),
                    "content_type": infer_content_type(item["source_path"], candidate),
                    "section_type": infer_section_type(candidate),
                    "knowledge_points": infer_knowledge_points(candidate),
                    "text": candidate,
                }
            )

    return selected


def main() -> None:
    ensure_pipeline_dirs()
    selected = build_selected_items()
    write_json(SELECTED_DIR / "selected_items.json", selected)
    write_json(
        SELECTED_DIR / "selected_manifest.json",
        {
            "input": relative_to_backend(CLEANED_DIR),
            "output": relative_to_backend(SELECTED_DIR / "selected_items.json"),
            "selected_count": len(selected),
        },
    )
    print(f"Input: {CLEANED_DIR}")
    print(f"Output: {SELECTED_DIR / 'selected_items.json'}")
    print(f"Selected items: {len(selected)}")


if __name__ == "__main__":
    main()
