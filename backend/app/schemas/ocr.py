from pydantic import BaseModel, Field


class OcrBlock(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class OcrResponse(BaseModel):
    ocr_text: str
    blocks: list[OcrBlock]
    corrected_text: str | None = None
    vision_text: str | None = None
    pix2text_text: str | None = None
    engine: str | None = None


class PageQuestionCandidate(BaseModel):
    question_no: str = ""
    question_text: str
    options: list[str] = []
    answer: str = ""
    solution: str = ""
    confidence: str = "medium"


class PageOcrResponse(BaseModel):
    page_text: str
    questions: list[PageQuestionCandidate]
    engine: str | None = None
    raw_text: str | None = None
