from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.ocr import OcrResponse
from app.services.ocr_service import OcrProcessingError, recognize_uploaded_image


router = APIRouter(tags=["ocr"])


@router.post("/ocr", response_model=OcrResponse)
async def extract_ocr_text(file: UploadFile = File(...)):
    try:
        return await recognize_uploaded_image(file)
    except OcrProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
