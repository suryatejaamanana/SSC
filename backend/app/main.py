from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.deps import get_db
from app.routers.v1 import admin as admin_router
from app.routers.v1 import attempts as attempts_router
from app.routers.v1 import auth as auth_router
from app.routers.v1 import exams as exams_router
from app.routers.v1 import media as media_router
from app.routers.v1 import subjects as subjects_router
from app.routers.v1 import topics as topics_router

settings = get_settings()

app = FastAPI(title="SSC CGL Practice Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(admin_router.router, prefix="/api/v1")
app.include_router(attempts_router.router, prefix="/api/v1")
app.include_router(exams_router.router, prefix="/api/v1")
app.include_router(subjects_router.router, prefix="/api/v1")
app.include_router(topics_router.router, prefix="/api/v1")
app.include_router(media_router.router, prefix="/api/v1")


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    return {"status": "ok", "database": db_status}
