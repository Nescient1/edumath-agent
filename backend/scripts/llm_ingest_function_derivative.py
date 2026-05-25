import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services.llm_service import get_llm_client, is_llm_enabled
from app.services.pix2text_service import Pix2TextResult, recognize_image_with_pix2text


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
RAW_LECTURES_DIR = DATA_DIR / "raw" / "lectures"
OUTPUT_ROOT = DATA_DIR / "llm_processed" / "function_derivative"
TOPIC_DIRS = {"function": "函数", "derivative": "导数"}
DEFAULT_KNOWLEDGE_POINTS = {
    "function": ["函数", "定义域", "值域", "单调性", "奇偶性", "零点", "函数图象"],
    "derivative": ["导数", "单调性", "极值", "最值", "恒成立", "不等式证明"],
}


def log_timing(event: str, seconds: float, **fields: Any) -> None:
    details = " ".join(
        f"{key}={str(value).replace(' ', '_')}"
        for key, value in fields.items()
        if value is not None
    )
    suffix = f" {details}" if details else ""
    print(f"[TIMING] event={event} seconds={seconds:.2f}{suffix}", flush=True)


def log_progress(message: str) -> None:
    print(message, flush=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_pdf_page(pdf_path: Path, page_no: int, image_path: Path, dpi: int) -> dict[str, Any]:
    import fitz

    image_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(pdf_path)) as document:
        page = document[page_no - 1]
        pixmap = page.get_pixmap(dpi=dpi, alpha=False)
        pixmap.save(str(image_path))
    return {"image_path": str(image_path), "width": pixmap.width, "height": pixmap.height, "dpi": dpi}


def relative_to_backend_data(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def extract_pdf_page_text(pdf_path: Path, page_no: int) -> dict[str, Any]:
    import fitz

    with fitz.open(str(pdf_path)) as document:
        page = document[page_no - 1]
        text = page.get_text("text").strip()
        blocks = page.get_text("blocks")
    return {"text": text, "char_count": len(text), "block_count": len(blocks)}


def pdf_page_count(pdf_path: Path) -> int:
    import fitz

    with fitz.open(str(pdf_path)) as document:
        return len(document)


def call_vision_model(image_path: Path, model: str | None) -> dict[str, str | None]:
    if not is_llm_enabled():
        return {"status": "skipped", "error": "LLM is not configured.", "text": ""}
    client = get_llm_client()
    if client is None:
        return {"status": "skipped", "error": "OpenAI-compatible client unavailable.", "text": ""}
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是高中数学资料 OCR 与结构化助手。请严格按图片内容输出 Markdown，"
                        "保留题号、题干、选项、解析、答案和数学公式。不要补充图片中不存在的内容。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别这页高中数学资料，输出 Markdown。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    ],
                },
            ],
            max_tokens=settings.llm_max_tokens,
            temperature=0.0,
        )
        return {"status": "success", "error": None, "text": (response.choices[0].message.content or "").strip()}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "text": ""}


def call_vision_figure_description(
    image_path: Path,
    model: str | None,
    *,
    source_name: str,
    page_no: int,
) -> dict[str, str | None]:
    if not is_llm_enabled():
        return {"status": "skipped", "error": "LLM is not configured.", "text": ""}
    client = get_llm_client()
    if client is None:
        return {"status": "skipped", "error": "OpenAI-compatible client unavailable.", "text": ""}
    try:
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        response = client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是高中数学题图理解助手。请只描述图片中可见的数学图形信息，"
                        "例如坐标轴、曲线、几何关系、标注、表格含义。不要解题，不要编造看不见的条件。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"资料：{source_name}，第 {page_no} 页。"
                                "请用 2-5 句话描述这个疑似题目配图，若不是题图请说明。"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                    ],
                },
            ],
            max_tokens=min(settings.llm_max_tokens, 800),
            temperature=0.0,
        )
        return {"status": "success", "error": None, "text": (response.choices[0].message.content or "").strip()}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "text": ""}


def _rect_to_tuple(rect: Any) -> tuple[float, float, float, float]:
    return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))


def _rect_area(rect: tuple[float, float, float, float]) -> float:
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def _rect_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    inter = _rect_area((x0, y0, x1, y1))
    union = _rect_area(a) + _rect_area(b) - inter
    return inter / union if union else 0.0


def _union_rect(rects: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    return (
        min(rect[0] for rect in rects),
        min(rect[1] for rect in rects),
        max(rect[2] for rect in rects),
        max(rect[3] for rect in rects),
    )


def _is_near_or_overlap(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    gap: float,
) -> bool:
    return not (
        a[2] + gap < b[0]
        or b[2] + gap < a[0]
        or a[3] + gap < b[1]
        or b[3] + gap < a[1]
    )


def _merge_near_rects(
    rects: list[tuple[float, float, float, float]],
    gap: float = 12.0,
) -> list[tuple[float, float, float, float]]:
    groups: list[list[tuple[float, float, float, float]]] = []
    for rect in rects:
        matched: list[int] = []
        for index, group in enumerate(groups):
            if any(_is_near_or_overlap(rect, item, gap) for item in group):
                matched.append(index)
        if not matched:
            groups.append([rect])
            continue
        first = matched[0]
        groups[first].append(rect)
        for index in reversed(matched[1:]):
            groups[first].extend(groups.pop(index))
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            if changed:
                break
            for j in range(i + 1, len(groups)):
                if _is_near_or_overlap(_union_rect(groups[i]), _union_rect(groups[j]), gap):
                    groups[i].extend(groups.pop(j))
                    changed = True
                    break
    return [_union_rect(group) for group in groups]


def detect_and_crop_figure_regions(
    pdf_path: Path,
    page_no: int,
    rendered_image_path: Path,
    assets_dir: Path,
    *,
    dpi: int,
    max_crops: int,
) -> list[dict[str, Any]]:
    import fitz
    from PIL import Image

    assets_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(pdf_path)) as document:
        page = document[page_no - 1]
        page_area = float(page.rect.width * page.rect.height)
        candidates: list[dict[str, Any]] = []

        page_dict = page.get_text("dict")
        for block in page_dict.get("blocks", []):
            if block.get("type") != 1:
                continue
            bbox = tuple(float(item) for item in block.get("bbox", (0, 0, 0, 0)))
            area = _rect_area(bbox)
            if area < 600 or area > page_area * 0.75:
                continue
            candidates.append(
                {
                    "bbox": bbox,
                    "region_type": "embedded_image",
                    "confidence": 0.9,
                    "detection_source": "pymupdf_image_block",
                }
            )

        drawing_rects: list[tuple[float, float, float, float]] = []
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None:
                continue
            bbox = _rect_to_tuple(rect)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            area = _rect_area(bbox)
            if width < 6 or height < 6 or area < 60:
                continue
            drawing_rects.append(bbox)

        for bbox in _merge_near_rects(drawing_rects):
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            area = _rect_area(bbox)
            if width < 35 or height < 28 or area < 1200 or area > page_area * 0.75:
                continue
            candidates.append(
                {
                    "bbox": bbox,
                    "region_type": "vector_figure",
                    "confidence": 0.62,
                    "detection_source": "pymupdf_drawings",
                }
            )

    deduped: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: _rect_area(item["bbox"]), reverse=True):
        if any(_rect_iou(candidate["bbox"], existing["bbox"]) > 0.65 for existing in deduped):
            continue
        deduped.append(candidate)
        if len(deduped) >= max_crops:
            break

    scale = dpi / 72.0
    margin = int(10 * scale)
    image = Image.open(rendered_image_path)
    width, height = image.size
    results: list[dict[str, Any]] = []
    for index, item in enumerate(deduped, start=1):
        bbox = item["bbox"]
        crop_box = (
            max(0, int(bbox[0] * scale) - margin),
            max(0, int(bbox[1] * scale) - margin),
            min(width, int(bbox[2] * scale) + margin),
            min(height, int(bbox[3] * scale) + margin),
        )
        if crop_box[2] - crop_box[0] < 30 or crop_box[3] - crop_box[1] < 30:
            continue
        crop_path = assets_dir / f"page_{page_no:03d}_figure_{index:02d}.png"
        image.crop(crop_box).save(crop_path)
        results.append(
            {
                "index": index,
                "region_type": item["region_type"],
                "confidence": item["confidence"],
                "detection_source": item["detection_source"],
                "bbox_pdf": [round(value, 2) for value in bbox],
                "bbox_pixel": list(crop_box),
                "image_path": str(crop_path),
                "relative_path": relative_to_backend_data(crop_path),
                "description_status": "pending",
                "description_error": None,
                "description": "",
            }
        )
    return results


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _complete_chat(
    client: Any,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    temperature: float = 0.0,
    prefer_json: bool = False,
) -> str:
    kwargs: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if prefer_json:
        try:
            response = client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        except Exception:
            # Some OpenAI-compatible providers do not support response_format.
            # Retry with plain chat completion instead of failing the page.
            pass
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _repair_json_output(client: Any, raw_content: str, fallback_text: str) -> dict[str, Any] | None:
    if not raw_content.strip():
        return None
    repair_messages = [
        {
            "role": "system",
            "content": (
                "你是 JSON 修复器。请把用户给出的模型输出修复成一个合法 JSON 对象。"
                "只输出 JSON，不要输出解释、Markdown 代码块或多余文本。"
                "字段必须包含 title, content_type, section_type, knowledge_points, difficulty, "
                "quality_label, cleaned_markdown, question_items。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请修复下面内容为合法 JSON。如果原内容缺少 cleaned_markdown，"
                "就用 fallback_text 作为 cleaned_markdown。\n\n"
                f"fallback_text:\n{fallback_text[:5000]}\n\n"
                f"raw_output:\n{raw_content[:12000]}"
            ),
        },
    ]
    try:
        repaired = _complete_chat(
            client,
            repair_messages,
            max_tokens=max(settings.llm_max_tokens, 4096),
            temperature=0.0,
            prefer_json=True,
        )
        return _extract_json(repaired)
    except Exception:
        return None


def _normalize_llm_result(parsed: dict[str, Any], topic: str, source_name: str, fallback_text: str) -> dict[str, Any]:
    parsed.setdefault("title", source_name)
    parsed.setdefault("cleaned_markdown", fallback_text)
    parsed.setdefault("knowledge_points", DEFAULT_KNOWLEDGE_POINTS.get(topic, []))
    parsed.setdefault("content_type", "lecture_note")
    parsed.setdefault("section_type", "mixed")
    parsed.setdefault("difficulty", "unknown")
    parsed.setdefault("quality_label", "pending_review")
    parsed.setdefault("question_items", [])
    if not isinstance(parsed.get("knowledge_points"), list):
        parsed["knowledge_points"] = [str(parsed["knowledge_points"])]
    if not isinstance(parsed.get("question_items"), list):
        parsed["question_items"] = []
    if not str(parsed.get("cleaned_markdown") or "").strip():
        parsed["cleaned_markdown"] = fallback_text
    return parsed


def llm_merge_page(
    *,
    topic: str,
    source_name: str,
    page_no: int,
    pymupdf_text: str,
    pix2text_markdown: str,
    vision_markdown: str,
    figure_regions: list[dict[str, Any]] | None = None,
    vision_first: bool = False,
) -> dict[str, Any]:
    fallback_text = pix2text_markdown.strip() or pymupdf_text.strip() or vision_markdown.strip()
    if not is_llm_enabled():
        return {
            "status": "fallback",
            "error": "LLM is not configured.",
            "result": {
                "title": source_name,
                "content_type": "lecture_note",
                "section_type": "unknown",
                "knowledge_points": DEFAULT_KNOWLEDGE_POINTS.get(topic, []),
                "difficulty": "unknown",
                "quality_label": "pending_review",
                "cleaned_markdown": fallback_text,
                "question_items": [],
            },
        }

    client = get_llm_client()
    if client is None:
        return {"status": "fallback", "error": "LLM client unavailable.", "result": {"cleaned_markdown": fallback_text}}

    prompt = {
        "source_name": source_name,
        "topic": TOPIC_DIRS.get(topic, topic),
        "page_no": page_no,
        "fusion_policy": "vision_first" if vision_first else "balanced",
        "pymupdf_text": pymupdf_text[:4500],
        "pix2text_markdown": pix2text_markdown[:6500],
        "vision_markdown": vision_markdown[:4500],
        "figure_regions": [
            {
                "index": item.get("index"),
                "region_type": item.get("region_type"),
                "confidence": item.get("confidence"),
                "image_path": item.get("relative_path"),
                "description": item.get("description"),
            }
            for item in (figure_regions or [])
        ],
    }
    source_policy = (
        "优先参考视觉模型的页面理解和结构；公式仍可参考 Pix2Text；中文细节可参考 PyMuPDF。"
        if vision_first
        else "公式优先参考 Pix2Text 的 LaTeX；中文叙述优先参考 PyMuPDF；视觉结果用于结构校对。"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "你是高中数学资料清洗与结构化专家。任务是融合 PyMuPDF、Pix2Text 和视觉模型候选结果，"
                "生成可信、清晰、适合进入 RAG 知识库的 Markdown。优先保留原文题目、方法、例题、解析，"
                f"不要编造不存在的内容。{source_policy}"
                "如果候选互相矛盾，用 [待校对: ...] 标记。必须只输出一个合法 JSON 对象，"
                "不要输出 Markdown 代码块、解释文字或 JSON 之外的任何内容。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请输出如下 JSON：\n"
                "{\n"
                '  "title": "资料页标题",\n'
                '  "content_type": "lecture_note|exercise|exam_solution|knowledge_summary",\n'
                '  "section_type": "method|example|solution|concept|mixed",\n'
                '  "knowledge_points": ["知识点1"],\n'
                '  "difficulty": "easy|medium|hard|unknown",\n'
                '  "quality_label": "high|medium|low|pending_review",\n'
                '  "cleaned_markdown": "清洗后的 Markdown",\n'
                '  "question_items": [\n'
                '    {"question": "题干", "options": ["A...", "B..."], "answer": "答案", "solution": "解析", '
                '"knowledge_points": ["知识点"], "image_paths": ["backend/data 相对路径"], '
                '"image_descriptions": ["题图描述"]}\n'
                "  ]\n"
                "}\n\n"
                f"候选输入：\n{json.dumps(prompt, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        content = _complete_chat(
            client,
            messages,
            max_tokens=max(settings.llm_max_tokens, 4096),
            temperature=0.0,
            prefer_json=True,
        )
        parsed = _extract_json(content)
        if not parsed:
            parsed = _repair_json_output(client, content, fallback_text)
        if not parsed:
            raise ValueError("LLM output is not valid JSON.")
        parsed = _normalize_llm_result(parsed, topic, source_name, fallback_text)
        return {"status": "success", "error": None, "result": parsed, "raw": content}
    except Exception as exc:
        return {
            "status": "fallback",
            "error": str(exc),
            "result": {
                "title": source_name,
                "content_type": "lecture_note",
                "section_type": "mixed",
                "knowledge_points": DEFAULT_KNOWLEDGE_POINTS.get(topic, []),
                "difficulty": "unknown",
                "quality_label": "pending_review",
                "cleaned_markdown": fallback_text,
                "question_items": [],
            },
        }


def split_markdown_to_chunks(text: str, target_chars: int = 1200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?=\n#{1,3}\s+|\n\d+[．.、])", "\n" + text)
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) + 2 <= target_chars:
            current = f"{current}\n\n{part}".strip()
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def connect_pg():
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Missing dependency: psycopg. Install psycopg[binary].") from exc
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "edumath_agent"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def upsert_document(cur, path: Path, topic: str, file_hash: str) -> str:
    source_path = str(path.relative_to(BACKEND_DIR))
    cur.execute(
        """
        INSERT INTO documents (source_name, source_path, file_type, file_hash, subject, topic, source_category, status, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'processed', %s::jsonb)
        ON CONFLICT (source_path, file_hash)
        DO UPDATE SET status='processed', updated_at=now(), metadata=EXCLUDED.metadata
        RETURNING id
        """,
        (
            path.name,
            source_path,
            path.suffix.lower(),
            file_hash,
            "高中数学",
            TOPIC_DIRS.get(topic, topic),
            "lecture",
            json.dumps({"pipeline": "llm_ingest_function_derivative_v1"}, ensure_ascii=False),
        ),
    )
    return str(cur.fetchone()[0])


def insert_page_to_db(cur, *, document_id: str, page_index: int, page_data: dict[str, Any]) -> None:
    llm_result = page_data["llm"]["result"]
    cur.execute(
        """
        SELECT id
        FROM text_blocks
        WHERE document_id = %s
          AND metadata->>'page_no' = %s
        """,
        (document_id, str(page_index)),
    )
    old_block_ids = [row[0] for row in cur.fetchall()]
    if old_block_ids:
        cur.execute("DELETE FROM rag_chunks WHERE text_block_id = ANY(%s)", (old_block_ids,))
        cur.execute("DELETE FROM question_items WHERE text_block_id = ANY(%s)", (old_block_ids,))
        cur.execute("DELETE FROM llm_processing_runs WHERE text_block_id = ANY(%s)", (old_block_ids,))
        cur.execute("DELETE FROM text_blocks WHERE id = ANY(%s)", (old_block_ids,))

    cur.execute(
        """
        INSERT INTO extraction_runs (document_id, extractor_type, extractor_version, status, quality_label, warnings)
        VALUES (%s, 'pymupdf_pix2text_llm', 'v1', %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            document_id,
            "success" if page_data["llm"]["status"] == "success" else "fallback",
            llm_result.get("quality_label", "pending_review"),
            json.dumps(page_data.get("warnings", []), ensure_ascii=False),
        ),
    )
    extraction_run_id = str(cur.fetchone()[0])
    cur.execute(
        """
        INSERT INTO text_blocks (
            document_id, extraction_run_id, block_index, block_type, raw_text, cleaned_text,
            llm_rewritten_text, quality_label, metadata
        )
        VALUES (%s, %s, %s, 'page', %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (document_id, extraction_run_id, block_index) DO NOTHING
        RETURNING id
        """,
        (
            document_id,
            extraction_run_id,
            page_index,
            page_data["pymupdf"]["text"],
            llm_result.get("cleaned_markdown", ""),
            llm_result.get("cleaned_markdown", ""),
            llm_result.get("quality_label", "pending_review"),
            json.dumps(
                {
                    "page_no": page_index,
                    "pymupdf": {k: v for k, v in page_data["pymupdf"].items() if k != "text"},
                    "pix2text_markdown": page_data["pix2text"].get("markdown", ""),
                    "vision_status": page_data["vision"].get("status"),
                    "vision_error": page_data["vision"].get("error"),
                    "image_path": page_data["rendered_image"].get("image_path"),
                    "page_image_path": page_data.get("page_image_relative_path"),
                    "figures": page_data.get("figures", []),
                },
                ensure_ascii=False,
            ),
        ),
    )
    row = cur.fetchone()
    text_block_id = str(row[0]) if row else None

    cur.execute(
        """
        INSERT INTO llm_processing_runs (document_id, text_block_id, stage, model, prompt_version, status, error_message, result)
        VALUES (%s, %s, 'merge_clean_page', %s, 'v1', %s, %s, %s::jsonb)
        """,
        (
            document_id,
            text_block_id,
            settings.openai_model,
            page_data["llm"]["status"],
            page_data["llm"].get("error"),
            json.dumps(llm_result, ensure_ascii=False),
        ),
    )

    chunks = split_markdown_to_chunks(llm_result.get("cleaned_markdown", ""))
    for chunk_index, chunk_text in enumerate(chunks, start=1):
        cur.execute(
            """
            INSERT INTO rag_chunks (
                document_id, text_block_id, chunk_index, chunk_text, content_type, section_type,
                knowledge_points, token_count, quality_label, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb)
            """,
            (
                document_id,
                text_block_id,
                chunk_index,
                chunk_text,
                llm_result.get("content_type", "lecture_note"),
                llm_result.get("section_type", "mixed"),
                json.dumps(llm_result.get("knowledge_points", []), ensure_ascii=False),
                max(1, len(chunk_text) // 2),
                llm_result.get("quality_label", "pending_review"),
                json.dumps(
                    {
                        "page_no": page_index,
                        "source": "llm_merged",
                        "page_image_path": page_data.get("page_image_relative_path"),
                        "figures": page_data.get("figures", []),
                    },
                    ensure_ascii=False,
                ),
            ),
        )

    page_figure_paths = [
        item.get("relative_path") for item in page_data.get("figures", []) if item.get("relative_path")
    ]
    page_figure_descriptions = [
        item.get("description") for item in page_data.get("figures", []) if item.get("description")
    ]
    for question in llm_result.get("question_items", []) or []:
        question_text = (question.get("question") or question.get("question_text") or "").strip()
        if not question_text:
            continue
        image_paths = question.get("image_paths") or page_figure_paths
        image_descriptions = question.get("image_descriptions") or page_figure_descriptions
        cur.execute(
            """
            INSERT INTO question_items (
                document_id, text_block_id, question_text, options, answer, solution,
                knowledge_points, difficulty, question_type, quality_label, metadata
            )
            VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb)
            """,
            (
                document_id,
                text_block_id,
                question_text,
                json.dumps(question.get("options", []), ensure_ascii=False),
                question.get("answer") or "",
                question.get("solution") or "",
                json.dumps(question.get("knowledge_points") or llm_result.get("knowledge_points", []), ensure_ascii=False),
                question.get("difficulty") or llm_result.get("difficulty") or "unknown",
                question.get("question_type") or "extracted",
                llm_result.get("quality_label", "pending_review"),
                json.dumps(
                    {
                        "page_no": page_index,
                        "source": "llm_extracted",
                        "page_image_path": page_data.get("page_image_relative_path"),
                        "image_paths": image_paths,
                        "image_descriptions": image_descriptions,
                        "figure_candidates": page_data.get("figures", []),
                    },
                    ensure_ascii=False,
                ),
            ),
        )


def list_input_files(limit: int | None, topic_filter: str = "all") -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for topic in ("function", "derivative"):
        if topic_filter != "all" and topic != topic_filter:
            continue
        topic_dir = RAW_LECTURES_DIR / topic
        if not topic_dir.exists():
            continue
        files.extend((topic, path) for path in sorted(topic_dir.glob("*.pdf")))
        files.extend((topic, path) for path in sorted(topic_dir.glob("*.txt")))
        files.extend((topic, path) for path in sorted(topic_dir.glob("*.md")))
    return files[:limit] if limit else files


def process_pdf(
    topic: str,
    path: Path,
    *,
    max_pages: int,
    dpi: int,
    use_vision: bool,
    vision_model: str | None,
    vision_first: bool,
    max_figure_crops: int,
    skip_existing_success: bool,
    pix2text_mode: str,
) -> dict[str, Any]:
    document_start = time.perf_counter()
    doc_dir = OUTPUT_ROOT / topic / path.stem
    pages_dir = doc_dir / "pages"
    total_pages = pdf_page_count(path)
    page_count = total_pages if max_pages <= 0 else min(total_pages, max_pages)
    document_result = {
        "source_path": str(path.relative_to(BACKEND_DIR)),
        "topic": topic,
        "file_hash": file_sha256(path),
        "page_count_total": total_pages,
        "page_count_processed": page_count,
        "pages": [],
    }
    for page_no in range(1, page_count + 1):
        page_start = time.perf_counter()
        page_dir = doc_dir / f"page_{page_no:03d}"
        page_result_path = page_dir / "page_result.json"
        if skip_existing_success and page_result_path.exists():
            try:
                existing = json.loads(page_result_path.read_text(encoding="utf-8"))
                if existing.get("llm", {}).get("status") == "success":
                    log_progress(f"  skip existing success page {page_no}/{page_count}")
                    log_timing(
                        "page.skip_existing_success",
                        time.perf_counter() - page_start,
                        topic=topic,
                        source=path.name,
                        page=page_no,
                    )
                    document_result["pages"].append(existing)
                    continue
            except (json.JSONDecodeError, OSError):
                pass
        log_progress(f"  page {page_no}/{page_count}")
        assets_dir = page_dir / "assets"
        step_start = time.perf_counter()
        pymupdf = extract_pdf_page_text(path, page_no)
        log_timing(
            "page.pymupdf",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            chars=pymupdf.get("char_count"),
            blocks=pymupdf.get("block_count"),
        )
        image_path = pages_dir / f"page_{page_no:03d}_{dpi}dpi.png"
        step_start = time.perf_counter()
        rendered = render_pdf_page(path, page_no, image_path, dpi)
        log_timing(
            "page.render",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            width=rendered.get("width"),
            height=rendered.get("height"),
        )
        step_start = time.perf_counter()
        pix2text_status = "success"
        should_run_pix2text = pix2text_mode == "always" or (
            pix2text_mode == "auto" and pymupdf.get("char_count", 0) < 200
        )
        if should_run_pix2text:
            pix2text = recognize_image_with_pix2text(image_path)
            pix2text_status = "failed" if pix2text.error else "success"
        else:
            pix2text = Pix2TextResult(text="", error=None)
            pix2text_status = "skipped"
        log_timing(
            "page.pix2text",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            mode=pix2text_mode,
            status=pix2text_status,
            chars=len(pix2text.text),
        )
        step_start = time.perf_counter()
        figures = detect_and_crop_figure_regions(
            path,
            page_no,
            image_path,
            assets_dir,
            dpi=dpi,
            max_crops=max_figure_crops,
        )
        log_timing(
            "page.detect_figures",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            figures=len(figures),
        )
        step_start = time.perf_counter()
        vision = call_vision_model(image_path, vision_model) if use_vision else {
            "status": "skipped",
            "error": "vision disabled",
            "text": "",
        }
        log_timing(
            "page.vision",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            status=vision.get("status"),
            chars=len(vision.get("text") or ""),
        )
        if use_vision:
            figures_start = time.perf_counter()
            for figure in figures:
                step_start = time.perf_counter()
                description = call_vision_figure_description(
                    Path(figure["image_path"]),
                    vision_model,
                    source_name=path.name,
                    page_no=page_no,
                )
                figure["description_status"] = description.get("status")
                figure["description_error"] = description.get("error")
                figure["description"] = description.get("text") or ""
                log_timing(
                    "page.figure_vision",
                    time.perf_counter() - step_start,
                    topic=topic,
                    source=path.name,
                    page=page_no,
                    figure=figure.get("index"),
                    status=figure.get("description_status"),
                    chars=len(figure.get("description") or ""),
                )
            log_timing(
                "page.figure_vision_total",
                time.perf_counter() - figures_start,
                topic=topic,
                source=path.name,
                page=page_no,
                figures=len(figures),
            )
        step_start = time.perf_counter()
        llm = llm_merge_page(
            topic=topic,
            source_name=path.name,
            page_no=page_no,
            pymupdf_text=pymupdf["text"],
            pix2text_markdown=pix2text.text,
            vision_markdown=vision.get("text") or "",
            figure_regions=figures,
            vision_first=vision_first,
        )
        log_timing(
            "page.llm_merge",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
            status=llm.get("status"),
            questions=len((llm.get("result") or {}).get("question_items") or []),
        )
        page_data = {
            "page_no": page_no,
            "pymupdf": pymupdf,
            "rendered_image": rendered,
            "page_image_relative_path": relative_to_backend_data(image_path),
            "pix2text": {
                "status": pix2text_status,
                "mode": pix2text_mode,
                "error": pix2text.error,
                "markdown": pix2text.text,
                "char_count": len(pix2text.text),
            },
            "vision": {
                "status": vision.get("status"),
                "error": vision.get("error"),
                "markdown": vision.get("text") or "",
                "char_count": len(vision.get("text") or ""),
            },
            "figures": figures,
            "llm": llm,
        }
        step_start = time.perf_counter()
        write_text(page_dir / "pymupdf.md", pymupdf["text"])
        write_text(page_dir / "pix2text.md", pix2text.text)
        write_text(page_dir / "vision.md", vision.get("text") or "")
        write_text(page_dir / "merged.md", llm["result"].get("cleaned_markdown", ""))
        write_json(page_dir / "figures.json", figures)
        write_json(page_dir / "page_result.json", page_data)
        log_timing(
            "page.write_files",
            time.perf_counter() - step_start,
            topic=topic,
            source=path.name,
            page=page_no,
        )
        log_timing(
            "page.total",
            time.perf_counter() - page_start,
            topic=topic,
            source=path.name,
            page=page_no,
            llm_status=llm.get("status"),
            questions=len((llm.get("result") or {}).get("question_items") or []),
            figures=len(figures),
        )
        document_result["pages"].append(page_data)
    write_json(doc_dir / "document_result.json", document_result)
    log_timing(
        "document.total",
        time.perf_counter() - document_start,
        topic=topic,
        source=path.name,
        pages=page_count,
    )
    return document_result


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="LLM-assisted ingestion for function/derivative lecture materials.")
    parser.add_argument("--limit", type=int, default=None, help="Max files to process. Default: all files.")
    parser.add_argument(
        "--topic",
        choices=["all", "function", "derivative"],
        default="all",
        help="Which imported topic to process.",
    )
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages per PDF. Use 0 for all pages.")
    parser.add_argument("--dpi", type=int, default=300, help="PDF render DPI.")
    parser.add_argument("--use-vision", action="store_true", help="Also call a vision-capable OpenAI-compatible model.")
    parser.add_argument("--vision-model", default=None, help="Vision model override. Defaults to OPENAI_MODEL, e.g. mimo-v2.5.")
    parser.add_argument("--max-figure-crops", type=int, default=4, help="Max suspected figure crops per page.")
    parser.add_argument(
        "--pix2text-mode",
        choices=["always", "auto", "off"],
        default="always",
        help=(
            "Pix2Text strategy. always=quality first; "
            "auto=only when PyMuPDF text is very sparse; off=fast ingestion."
        ),
    )
    parser.add_argument(
        "--vision-first",
        action="store_true",
        help="Ask the merge LLM to prioritize vision model output when available.",
    )
    parser.add_argument("--write-db", action="store_true", help="Write documents, blocks, chunks, and LLM results to PostgreSQL.")
    parser.add_argument(
        "--allow-fallback-db",
        action="store_true",
        help="Allow fallback pages to be written to PostgreSQL. By default only successful LLM-merged pages are written.",
    )
    parser.add_argument(
        "--skip-existing-success",
        action="store_true",
        help="Reuse local page_result.json when the page already has successful LLM output.",
    )
    args = parser.parse_args()
    use_vision = args.use_vision or args.vision_first

    files = list_input_files(args.limit, args.topic)
    if not files:
        raise RuntimeError(f"No imported lecture PDFs found under {RAW_LECTURES_DIR}. Run import_raw_temp_topics.py first.")

    results = []
    skipped_db_pages = 0
    written_db_pages = 0
    conn = connect_pg() if args.write_db else None
    try:
        for topic, path in files:
            log_progress(f"processing {path}")
            result = process_pdf(
                topic,
                path,
                max_pages=args.max_pages,
                dpi=args.dpi,
                use_vision=use_vision,
                vision_model=args.vision_model,
                vision_first=args.vision_first,
                max_figure_crops=args.max_figure_crops,
                skip_existing_success=args.skip_existing_success,
                pix2text_mode=args.pix2text_mode,
            )
            results.append(result)
            if conn is not None:
                with conn.cursor() as cur:
                    document_id = upsert_document(cur, path, topic, result["file_hash"])
                    for page_data in result["pages"]:
                        if page_data["llm"]["status"] != "success" and not args.allow_fallback_db:
                            skipped_db_pages += 1
                            log_progress(
                                f"  skip db write page {page_data['page_no']} status={page_data['llm']['status']}"
                            )
                            continue
                        step_start = time.perf_counter()
                        insert_page_to_db(
                            cur,
                            document_id=document_id,
                            page_index=page_data["page_no"],
                            page_data=page_data,
                        )
                        written_db_pages += 1
                        log_timing(
                            "page.db_write",
                            time.perf_counter() - step_start,
                            topic=topic,
                            source=path.name,
                            page=page_data["page_no"],
                        )
                conn.commit()
    finally:
        if conn is not None:
            conn.close()

    manifest = {
        "input_dir": str(RAW_LECTURES_DIR.relative_to(BACKEND_DIR)),
        "output_dir": str(OUTPUT_ROOT.relative_to(BACKEND_DIR)),
        "processed_files": len(results),
        "topic": args.topic,
        "max_pages": args.max_pages,
        "skip_existing_success": args.skip_existing_success,
        "use_vision": use_vision,
        "vision_model": args.vision_model or settings.openai_model,
        "vision_first": args.vision_first,
        "max_figure_crops": args.max_figure_crops,
        "pix2text_mode": args.pix2text_mode,
        "write_db": args.write_db,
        "allow_fallback_db": args.allow_fallback_db,
        "processed_pages": sum(len(item["pages"]) for item in results),
        "llm_success_pages": sum(
            1 for item in results for page in item["pages"] if page["llm"]["status"] == "success"
        ),
        "llm_fallback_pages": sum(
            1 for item in results for page in item["pages"] if page["llm"]["status"] != "success"
        ),
        "db_written_pages": written_db_pages,
        "skipped_db_pages": skipped_db_pages,
        "extracted_question_items": sum(
            len((page["llm"]["result"] or {}).get("question_items") or [])
            for item in results
            for page in item["pages"]
        ),
        "results": [
            {
                "source_path": item["source_path"],
                "topic": item["topic"],
                "pages": item["page_count_processed"],
            }
            for item in results
        ],
    }
    write_json(OUTPUT_ROOT / "ingest_manifest.json", manifest)
    print(f"processed_files={len(results)} output={OUTPUT_ROOT}", flush=True)
    if args.write_db:
        print("database_write=enabled", flush=True)
        print(f"db_written_pages={written_db_pages}", flush=True)
        print(f"skipped_db_pages={skipped_db_pages}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
