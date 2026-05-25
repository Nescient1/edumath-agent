from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from app.core.config import STORAGE_DIR, settings
from app.services.llm_service import is_enabled_flag


class Pix2TextUnavailable(RuntimeError):
    pass


@dataclass
class Pix2TextResult:
    text: str
    raw: Any | None = None
    error: str | None = None


def is_pix2text_enabled() -> bool:
    return is_enabled_flag(settings.enable_pix2text_ocr)


def _prepare_runtime_dirs() -> None:
    ultralytics_dir = STORAGE_DIR / "ultralytics"
    pix2text_dir = STORAGE_DIR / "pix2text"
    ultralytics_dir.mkdir(parents=True, exist_ok=True)
    pix2text_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("YOLO_CONFIG_DIR", str(ultralytics_dir))
    os.environ.setdefault("ULTRALYTICS_SETTINGS_DIR", str(ultralytics_dir))
    os.environ.setdefault("PIX2TEXT_HOME", str(pix2text_dir))


def is_pix2text_installed() -> bool:
    _prepare_runtime_dirs()
    try:
        import pix2text  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def get_pix2text_engine() -> Any:
    _prepare_runtime_dirs()
    try:
        from pix2text import Pix2Text
    except ImportError as exc:
        raise Pix2TextUnavailable(
            "Pix2Text is not installed. Install it with `pip install pix2text`."
        ) from exc

    device = settings.pix2text_device.strip()
    try:
        if hasattr(Pix2Text, "from_config"):
            kwargs: dict[str, Any] = {}
            if device:
                kwargs["device"] = device
            return Pix2Text.from_config(**kwargs)
        return Pix2Text()
    except TypeError:
        return Pix2Text.from_config() if hasattr(Pix2Text, "from_config") else Pix2Text()


@lru_cache(maxsize=1)
def get_latex_ocr_engine() -> Any:
    _prepare_runtime_dirs()
    try:
        from pix2text import LatexOCR
    except ImportError as exc:
        raise Pix2TextUnavailable(
            "Pix2Text is not installed. Install it with `pip install pix2text`."
        ) from exc

    kwargs: dict[str, Any] = {"root": str(STORAGE_DIR / "pix2text")}
    device = settings.pix2text_device.strip()
    if device:
        kwargs["device"] = device
    return LatexOCR(**kwargs)


def _normalize_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "latex", "markdown"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if "items" in result and isinstance(result["items"], list):
            return "\n".join(_normalize_result(item) for item in result["items"]).strip()
    if isinstance(result, list):
        return "\n".join(_normalize_result(item) for item in result).strip()
    return str(result).strip()


def recognize_image_with_pix2text(
    image_path: Path,
    *,
    return_raw: bool = False,
) -> Pix2TextResult:
    if not image_path.exists():
        return Pix2TextResult(text="", error=f"Image not found: {image_path}")

    try:
        engine = get_pix2text_engine()
        recognize = getattr(engine, "recognize", None)
        if callable(recognize):
            try:
                raw = recognize(str(image_path), return_text=True)
            except TypeError:
                try:
                    raw = recognize(str(image_path), file_type="text_formula")
                except TypeError:
                    raw = recognize(str(image_path))
        else:
            raw = engine(str(image_path))
        return Pix2TextResult(
            text=_normalize_result(raw),
            raw=raw if return_raw else None,
        )
    except Exception as exc:
        return Pix2TextResult(text="", error=str(exc))


def recognize_formula_image_with_pix2text(
    image_path: Path,
    *,
    return_raw: bool = False,
) -> Pix2TextResult:
    if not image_path.exists():
        return Pix2TextResult(text="", error=f"Image not found: {image_path}")

    try:
        engine = get_latex_ocr_engine()
        recognize = getattr(engine, "recognize", None)
        if callable(recognize):
            raw = recognize(str(image_path))
        else:
            raw = engine(str(image_path))
        return Pix2TextResult(
            text=_normalize_result(raw),
            raw=raw if return_raw else None,
        )
    except Exception as exc:
        return Pix2TextResult(text="", error=str(exc))
