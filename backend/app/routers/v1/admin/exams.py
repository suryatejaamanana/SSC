from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.deps import get_db
from app.models.user import User
from app.schemas.exam import ExamCreate, ExamPublic, ExamUpdate
from app.services import exam_service

router = APIRouter(
    prefix="/admin/exams",
    tags=["admin:exams"],
    dependencies=[Depends(require_role("admin"))],
)


@router.post("", response_model=ExamPublic, status_code=status.HTTP_201_CREATED)
async def create_exam(
    payload: ExamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await exam_service.create_exam(db, payload, created_by=current_user.id)


@router.get("", response_model=list[ExamPublic])
async def list_exams(db: AsyncSession = Depends(get_db)):
    return await exam_service.list_exams(db)


@router.get("/{exam_id}", response_model=ExamPublic)
async def get_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    return await exam_service.get_exam(db, exam_id)


@router.patch("/{exam_id}", response_model=ExamPublic)
async def update_exam(exam_id: int, payload: ExamUpdate, db: AsyncSession = Depends(get_db)):
    return await exam_service.update_exam(db, exam_id, payload)


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    await exam_service.delete_exam(db, exam_id)


@router.post("/{exam_id}/publish", response_model=ExamPublic)
async def publish_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    return await exam_service.publish_exam(db, exam_id)
