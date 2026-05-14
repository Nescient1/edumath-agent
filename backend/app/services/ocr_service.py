from functools import lru_cache
from collections.abc import Mapping
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import STORAGE_DIR, UPLOADS_DIR
from app.schemas.ocr import OcrBlock, OcrResponse


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


async def recognize_uploaded_image(file: UploadFile) -> OcrResponse:
    suffix = _validate_upload(file)
    image_path = await _save_upload(file, suffix)

    try:
        engine = _get_ocr_engine()
        raw_result = _run_ocr(engine, image_path)
        blocks = _parse_ocr_result(raw_result)
    except OcrProcessingError:
        raise
    except Exception as exc:
        raise OcrProcessingError(f"OCR 识别失败：{exc}") from exc
    finally:
        image_path.unlink(missing_ok=True)

    if not blocks:
        raise OcrProcessingError("未识别到清晰文字，请更换图片后重试。")

    ocr_text = "\n".join(block.text for block in blocks)
    return OcrResponse(ocr_text=ocr_text, blocks=blocks)
