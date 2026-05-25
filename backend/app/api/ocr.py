from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.ocr import OcrResponse, PageOcrResponse
from app.services.ocr_service import (
    OcrProcessingError,
    recognize_uploaded_image,
    recognize_uploaded_page,
)


router = APIRouter(tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse)
async def extract_ocr_text(file: UploadFile = File(...)):
    try:
        return await recognize_uploaded_image(file)
    except OcrProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ocr/page", response_model=PageOcrResponse)
async def extract_page_questions(file: UploadFile = File(...)):
    try:
        return await recognize_uploaded_page(file)
    except OcrProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
