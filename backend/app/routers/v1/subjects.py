from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.deps import get_db
from app.schemas.subject import SubjectPublic
from app.services import subject_service

router = APIRouter(prefix="/subjects", tags=["subjects"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SubjectPublic])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    return await subject_service.list_subjects(db)
