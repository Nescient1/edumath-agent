from pydantic import BaseModel, Field


class OcrBlock(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class OcrResponse(BaseModel):
    ocr_text: str
    blocks: list[OcrBlock]
