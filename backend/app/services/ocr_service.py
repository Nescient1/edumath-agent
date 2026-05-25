from collections.abc import Mapping
from functools import lru_cache
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import STORAGE_DIR, UPLOADS_DIR, settings
from app.schemas.ocr import OcrBlock, OcrResponse, PageOcrResponse, PageQuestionCandidate
from app.services.llm_service import (
    is_enabled_flag,
    is_llm_enabled,
    safe_generate_text,
    safe_generate_vision_text,
)
from app.services.pix2text_service import (
    is_pix2text_enabled,
    is_pix2text_installed,
    recognize_image_with_pix2text,
    recognize_formula_image_with_pix2text,
)


ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024
PADDLEX_CACHE_DIR = STORAGE_DIR / "paddlex_cache"


class OcrProcessingError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _get_ocr_engine() -> Any:
    PADDLEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(PADDLEX_CACHE_DIR))
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MKLDNN_MODEL_BL", "True")

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OcrProcessingError(
            "PaddleOCR is not installed. Install backend requirements first."
        ) from exc

    try:
        return PaddleOCR(
            lang="ch",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except TypeError:
        return PaddleOCR(use_angle_cls=True, lang="ch")
    except Exception as exc:
        raise OcrProcessingError(f"Failed to initialize PaddleOCR: {exc}") from exc


def _validate_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise OcrProcessingError("仅支持 PNG、JPG、JPEG、BMP、WEBP 图片。")
    return suffix


async def _save_upload(file: UploadFile, suffix: str) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOADS_DIR / f"ocr_upload_{uuid4().hex}{suffix}"
    content = await file.read()
    if not content:
        raise OcrProcessingError("上传图片为空。")
    if len(content) > MAX_FILE_SIZE:
        raise OcrProcessingError("图片过大，请控制在 10MB 以内。")

    target.write_bytes(content)
    await file.seek(0)
    return target


def _parse_ocr_result(raw_result: Any) -> list[OcrBlock]:
    blocks: list[OcrBlock] = []
    if not raw_result:
        return blocks

    pages = raw_result if isinstance(raw_result, list) else [raw_result]
    for page in pages:
        if not isinstance(page, Mapping) or "rec_texts" not in page:
            continue

        texts = page.get("rec_texts") or []
        scores = page.get("rec_scores") or []
        for index, text_value in enumerate(texts):
            text = str(text_value).strip()
            if not text:
                continue

            try:
                confidence = float(scores[index])
            except (IndexError, TypeError, ValueError):
                confidence = 0.0

            blocks.append(
                OcrBlock(text=text, confidence=max(0.0, min(confidence, 1.0)))
            )

    if blocks:
        return blocks

    candidates = raw_result[0] if isinstance(raw_result, list) and raw_result else raw_result
    if not candidates:
        return blocks

    for item in candidates:
        if not item or len(item) < 2:
            continue
        text_info = item[1]
        if not isinstance(text_info, (list, tuple)) or len(text_info) < 2:
            continue
        text = str(text_info[0]).strip()
        try:
            confidence = float(text_info[1])
        except (TypeError, ValueError):
            confidence = 0.0

        if text:
            blocks.append(
                OcrBlock(text=text, confidence=max(0.0, min(confidence, 1.0)))
            )

    return blocks


def _run_ocr(engine: Any, image_path: Path) -> Any:
    image = str(image_path)
    predict = getattr(engine, "predict", None)
    if callable(predict):
        try:
            return predict(image, use_textline_orientation=False)
        except TypeError as exc:
            if "use_textline_orientation" not in str(exc):
                raise

    try:
        return engine.ocr(image, cls=True)
    except TypeError as exc:
        if "cls" in str(exc):
            return engine.ocr(image)
        raise


def recognize_math_text_with_pix2text(image_path: Path) -> str | None:
    if not is_pix2text_enabled() or not is_pix2text_installed():
        return None

    result = recognize_image_with_pix2text(image_path)
    if result.text.strip():
        return result.text.strip()

    result = recognize_formula_image_with_pix2text(image_path)
    if result.error or not result.text.strip():
        return None
    return result.text.strip()


def correct_ocr_text_with_llm(ocr_text: str) -> str | None:
    if (
        not ocr_text.strip()
        or not is_enabled_flag(settings.enable_llm_ocr_rewrite)
        or not is_llm_enabled()
    ):
        return None

    messages = [
        {
            "role": "system",
            "content": (
                "你是高中数学 OCR 文本整理助手。只修正明显 OCR 错字、断行和数学格式，"
                "不要解题，不要补充题目中不存在的条件。直接输出整理后的题目文本。"
            ),
        },
        {"role": "user", "content": ocr_text},
    ]
    corrected = safe_generate_text(
        messages=messages,
        max_tokens=512,
        temperature=0.0,
        fallback=None,
    )
    if corrected and corrected.strip() != ocr_text.strip():
        return corrected.strip()
    return None


def recognize_math_text_with_vision(image_path: Path) -> str | None:
    if (
        not is_enabled_flag(settings.enable_llm_ocr_vision)
        or not is_llm_enabled()
    ):
        return None

    prompt = (
        "请把图片中的高中数学题完整转写为可编辑文本。要求：\n"
        "1. 只输出题目文本，不要解题，不要解释；\n"
        "2. 保留题号、选项 A/B/C/D、括号、条件和换行结构；\n"
        "3. 数学公式尽量用 LaTeX 行内格式，例如 $y=\\ln x$；\n"
        "4. 不要补充图片中不存在的内容；看不清的地方用 [看不清] 标记；\n"
        "5. 如果有函数图像或几何图，只用一句话描述图像，不要臆造数值。"
    )
    text = safe_generate_vision_text(
        image_path=image_path,
        prompt=prompt,
        max_tokens=min(settings.llm_max_tokens, 2048),
        temperature=0.0,
        fallback=None,
    )
    return text.strip() if text and text.strip() else None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_options(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"(?=\b[A-D][\.．、])", value)
        return [part.strip() for part in parts if part.strip()]
    return []


def _normalize_page_questions(data: dict[str, Any], raw_text: str) -> list[PageQuestionCandidate]:
    raw_questions = data.get("questions") or []
    candidates: list[PageQuestionCandidate] = []
    if isinstance(raw_questions, list):
        for index, item in enumerate(raw_questions, start=1):
            if not isinstance(item, dict):
                continue
            question_text = str(item.get("question_text") or item.get("text") or "").strip()
            if not question_text:
                continue
            confidence = str(item.get("confidence") or "medium").strip().lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"
            candidates.append(
                PageQuestionCandidate(
                    question_no=str(item.get("question_no") or item.get("no") or index),
                    question_text=question_text,
                    options=_normalize_options(item.get("options")),
                    answer=str(item.get("answer") or "").strip(),
                    solution=str(item.get("solution") or "").strip(),
                    confidence=confidence,
                )
            )

    if candidates:
        return candidates

    page_text = str(data.get("page_text") or raw_text).strip()
    if not page_text:
        return []
    return [
        PageQuestionCandidate(
            question_no="1",
            question_text=page_text,
            confidence="low",
        )
    ]


def recognize_page_questions_with_vision(image_path: Path) -> PageOcrResponse | None:
    if (
        not is_enabled_flag(settings.enable_llm_ocr_vision)
        or not is_llm_enabled()
    ):
        return None

    prompt = (
        "你是高中数学整页试卷/讲义识别助手。请识别图片中的整页内容，并按题号拆分题目。\n"
        "只输出 JSON，不要 Markdown，不要解释。JSON 格式如下：\n"
        "{\n"
        '  "page_text": "按阅读顺序转写的整页文本",\n'
        '  "questions": [\n'
        "    {\n"
        '      "question_no": "题号或例题编号",\n'
        '      "question_text": "完整题干，公式用 LaTeX 行内格式 $...$",\n'
        '      "options": ["A. ...", "B. ..."],\n'
        '      "answer": "若页面上出现答案则填写，否则空字符串",\n'
        '      "solution": "若页面上出现解析则填写，否则空字符串",\n'
        '      "confidence": "high/medium/low"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "要求：\n"
        "1. 保留题目、选项、答案、解析的归属，不要把上一题解析当成下一题题干；\n"
        "2. 如果一页中有多道题，必须拆成多个 questions；\n"
        "3. 不要解题，不要补充图片中不存在的内容；\n"
        "4. 看不清的地方写 [看不清]，置信度设为 low；\n"
        "5. 函数图像或几何图只做简短文字描述并放进对应题干。"
    )
    raw_text = safe_generate_vision_text(
        image_path=image_path,
        prompt=prompt,
        max_tokens=min(settings.llm_max_tokens, 4096),
        temperature=0.0,
        fallback=None,
    )
    if not raw_text or not raw_text.strip():
        return None

    parsed = _extract_json_object(raw_text)
    if not parsed:
        return PageOcrResponse(
            page_text=raw_text.strip(),
            questions=[
                PageQuestionCandidate(
                    question_no="1",
                    question_text=raw_text.strip(),
                    confidence="low",
                )
            ],
            engine="vision",
            raw_text=raw_text.strip(),
        )

    page_text = str(parsed.get("page_text") or raw_text).strip()
    questions = _normalize_page_questions(parsed, raw_text)
    return PageOcrResponse(
        page_text=page_text,
        questions=questions,
        engine="vision",
        raw_text=raw_text.strip(),
    )


async def recognize_uploaded_image(file: UploadFile) -> OcrResponse:
    suffix = _validate_upload(file)
    image_path = await _save_upload(file, suffix)
    blocks: list[OcrBlock] = []
    paddle_error: str | None = None
    vision_text: str | None = None
    pix2text_text: str | None = None

    try:
        vision_text = recognize_math_text_with_vision(image_path)
        try:
            engine = _get_ocr_engine()
            raw_result = _run_ocr(engine, image_path)
            blocks = _parse_ocr_result(raw_result)
        except OcrProcessingError as exc:
            paddle_error = str(exc)
        except Exception as exc:
            paddle_error = f"OCR 识别失败：{exc}"

        pix2text_text = recognize_math_text_with_pix2text(image_path)
    finally:
        image_path.unlink(missing_ok=True)

    if not blocks and not pix2text_text and not vision_text:
        if paddle_error:
            raise OcrProcessingError(paddle_error)
        raise OcrProcessingError("未识别到清晰文字，请更换图片后重试。")

    ocr_text = "\n".join(block.text for block in blocks)
    if not ocr_text:
        fallback_text = pix2text_text or vision_text or ""
        ocr_text = fallback_text
        if fallback_text:
            blocks = [OcrBlock(text=fallback_text, confidence=0.0)]

    preferred_text = vision_text or pix2text_text or ocr_text
    llm_corrected_text = None if vision_text else correct_ocr_text_with_llm(preferred_text)
    corrected_text = llm_corrected_text or vision_text or pix2text_text
    engine = "vision" if vision_text else "pix2text" if pix2text_text else "paddleocr"
    return OcrResponse(
        ocr_text=ocr_text,
        blocks=blocks,
        corrected_text=corrected_text,
        vision_text=vision_text,
        pix2text_text=pix2text_text,
        engine=engine,
    )


async def recognize_uploaded_page(file: UploadFile) -> PageOcrResponse:
    suffix = _validate_upload(file)
    image_path = await _save_upload(file, suffix)
    try:
        page_result = recognize_page_questions_with_vision(image_path)
        if page_result:
            return page_result

        single_result = await recognize_uploaded_image(file)
        page_text = (
            single_result.corrected_text
            or single_result.vision_text
            or single_result.pix2text_text
            or single_result.ocr_text
        )
        return PageOcrResponse(
            page_text=page_text,
            questions=[
                PageQuestionCandidate(
                    question_no="1",
                    question_text=page_text,
                    confidence="low",
                )
            ],
            engine=single_result.engine,
            raw_text=page_text,
        )
    finally:
        image_path.unlink(missing_ok=True)
