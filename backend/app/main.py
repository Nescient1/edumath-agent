from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.diagnose import router as diagnose_router
from app.api.health import router as health_router
from app.api.materials import router as materials_router
from app.api.ocr import router as ocr_router
from app.api.practice import router as practice_router
from app.api.profiles import router as profiles_router
from app.api.questions import router as questions_router
from app.api.recommend import router as recommend_router
from app.core.config import PIPELINE_DATA_DIR, settings
from app.core.logging import configure_logging
from app.db.database import ensure_storage, init_db


configure_logging()
ensure_storage()
init_db()

app = FastAPI(title=settings.app_name, version=settings.version)

allow_origins = (
    ["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(ocr_router, prefix=settings.api_prefix)
app.include_router(questions_router, prefix=settings.api_prefix)
app.include_router(materials_router, prefix=settings.api_prefix)
app.include_router(diagnose_router, prefix=settings.api_prefix)
app.include_router(recommend_router, prefix=settings.api_prefix)
app.include_router(profiles_router, prefix=settings.api_prefix)
app.include_router(practice_router, prefix=settings.api_prefix)

PIPELINE_DATA_DIR.mkdir(parents=True, exist_ok=True)
app.mount(
    f"{settings.api_prefix}/media",
    StaticFiles(directory=str(PIPELINE_DATA_DIR)),
    name="pipeline_media",
)
