from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from app.core.config import settings


def is_enabled_flag(value: str | bool | int | None) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_llm_enabled() -> bool:
    return bool(settings.openai_api_key and settings.openai_model)


def get_llm_client() -> Any | None:
    if not is_llm_enabled():
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    kwargs: dict[str, Any] = {
        "api_key": settings.openai_api_key,
        "timeout": settings.llm_timeout_seconds,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def generate_text(
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
    temperature: float = 0.2,
) -> str:
    client = get_llm_client()
    if client is None:
        raise RuntimeError("LLM is not configured.")

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        max_tokens=max_tokens or settings.llm_max_tokens,
        temperature=temperature,
    )
    content = response.choices[0].message.content or ""
    return content.strip()


def safe_generate_text(
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
    temperature: float = 0.2,
    fallback: str | None = None,
) -> str | None:
    try:
        content = generate_text(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception:
        return fallback
    return content or fallback


def generate_vision_text(
    image_path: str | Path,
    prompt: str,
    max_tokens: int | None = None,
    temperature: float = 0.0,
) -> str:
    path = Path(image_path)
    if not path.exists():
        raise RuntimeError(f"Image not found: {path}")

    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    image_base64 = base64.b64encode(path.read_bytes()).decode("ascii")
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}",
                    },
                },
            ],
        }
    ]
    return generate_text(
        messages=messages,
        max_tokens=max_tokens or settings.llm_max_tokens,
        temperature=temperature,
    )


def safe_generate_vision_text(
    image_path: str | Path,
    prompt: str,
    max_tokens: int | None = None,
    temperature: float = 0.0,
    fallback: str | None = None,
) -> str | None:
    try:
        content = generate_vision_text(
            image_path=image_path,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception:
        return fallback
    return content or fallback
