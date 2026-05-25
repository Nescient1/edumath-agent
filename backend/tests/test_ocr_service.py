import pytest
from io import BytesIO

fastapi = pytest.importorskip("fastapi")
UploadFile = fastapi.UploadFile

from app.services.ocr_service import (
    OcrProcessingError,
    correct_ocr_text_with_llm,
    recognize_math_text_with_pix2text,
    recognize_math_text_with_vision,
    _parse_ocr_result,
    _validate_upload,
)


def test_parse_ocr_result_extracts_text_and_confidence():
    raw_result = [
        [
            [[[0, 0], [1, 0], [1, 1], [0, 1]], ("函数单调区间", 0.98)],
            [[[0, 2], [1, 2], [1, 3], [0, 3]], ("求极值", 0.87)],
        ]
    ]

    blocks = _parse_ocr_result(raw_result)

    assert [block.text for block in blocks] == ["函数单调区间", "求极值"]
    assert blocks[0].confidence == 0.98
    assert blocks[1].confidence == 0.87


def test_parse_ocr_result_extracts_paddleocr_v3_result():
    raw_result = [
        {
            "rec_texts": ["函数单调区间", "求极值"],
            "rec_scores": [0.98, 0.87],
        }
    ]

    blocks = _parse_ocr_result(raw_result)

    assert [block.text for block in blocks] == ["函数单调区间", "求极值"]
    assert blocks[0].confidence == 0.98
    assert blocks[1].confidence == 0.87


def test_validate_upload_rejects_non_image_extension():
    upload = UploadFile(filename="note.txt", file=BytesIO(b"test"))

    with pytest.raises(OcrProcessingError):
        _validate_upload(upload)


def test_ocr_rewrite_disabled_by_default():
    assert correct_ocr_text_with_llm("f(x)=xe^x") is None


def test_ocr_rewrite_enabled_uses_safe_fallback(monkeypatch):
    from app.core.config import settings

    settings.openai_api_key = "test-key"
    settings.openai_model = "mimo-v2.5"
    settings.enable_llm_ocr_rewrite = "1"

    monkeypatch.setattr(
        "app.services.ocr_service.safe_generate_text",
        lambda *args, **kwargs: "f(x)=x e^x",
    )

    assert correct_ocr_text_with_llm("f(x)=xe^x") == "f(x)=x e^x"


def test_pix2text_math_text_prefers_full_image_result(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services.pix2text_service import Pix2TextResult

    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"fake")
    settings.enable_pix2text_ocr = "1"

    monkeypatch.setattr(
        "app.services.ocr_service.is_pix2text_installed",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.ocr_service.recognize_image_with_pix2text",
        lambda path: Pix2TextResult(text="A. $y=-x^2$\nB. $y=\\ln x$"),
    )
    monkeypatch.setattr(
        "app.services.ocr_service.recognize_formula_image_with_pix2text",
        lambda path: Pix2TextResult(text="$x^2$"),
    )

    assert recognize_math_text_with_pix2text(image_path) == "A. $y=-x^2$\nB. $y=\\ln x$"


def test_vision_math_text_uses_api_when_enabled(monkeypatch, tmp_path):
    from app.core.config import settings

    image_path = tmp_path / "question.png"
    image_path.write_bytes(b"fake")
    settings.openai_api_key = "test-key"
    settings.openai_model = "mimo-v2.5"
    settings.enable_llm_ocr_vision = "1"

    monkeypatch.setattr(
        "app.services.ocr_service.safe_generate_vision_text",
        lambda *args, **kwargs: "2. 下列函数在其定义域内单调递增的是\nA. $y=-\\frac{1}{x}$",
    )

    assert "单调递增" in recognize_math_text_with_vision(image_path)
