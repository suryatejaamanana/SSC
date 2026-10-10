from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.deps import get_db
from app.schemas.exam import ExamPublic
from app.services import exam_service

router = APIRouter(prefix="/exams", tags=["exams"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ExamPublic])
async def list_published_exams(db: AsyncSession = Depends(get_db)):
    return await exam_service.list_published_exams(db)


@router.get("/{exam_id}", response_model=ExamPublic)
async def get_published_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    return await exam_service.get_published_exam(db, exam_id)
