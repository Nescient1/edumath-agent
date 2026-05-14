from fastapi import APIRouter

from app.schemas.diagnose import DiagnoseRequest, DiagnoseResponse
from app.services.diagnose_service import diagnose_wrong_question


router = APIRouter(tags=["diagnose"])


@router.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(req: DiagnoseRequest):
    return diagnose_wrong_question(req)
