import pytest
from io import BytesIO

fastapi = pytest.importorskip("fastapi")
UploadFile = fastapi.UploadFile

from app.services.ocr_service import (
    OcrProcessingError,
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
