from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.deps import get_db
from app.schemas.subject import SubjectCreate, SubjectPublic, SubjectUpdate
from app.services import subject_service

router = APIRouter(
    prefix="/admin/subjects",
    tags=["admin:subjects"],
    dependencies=[Depends(require_role("admin"))],
)


@router.post("", response_model=SubjectPublic, status_code=status.HTTP_201_CREATED)
async def create_subject(payload: SubjectCreate, db: AsyncSession = Depends(get_db)):
    return await subject_service.create_subject(db, payload)


@router.get("", response_model=list[SubjectPublic])
async def list_subjects(db: AsyncSession = Depends(get_db)):
    return await subject_service.list_subjects(db)


@router.get("/{subject_id}", response_model=SubjectPublic)
async def get_subject(subject_id: int, db: AsyncSession = Depends(get_db)):
    return await subject_service.get_subject(db, subject_id)


@router.patch("/{subject_id}", response_model=SubjectPublic)
async def update_subject(subject_id: int, payload: SubjectUpdate, db: AsyncSession = Depends(get_db)):
    return await subject_service.update_subject(db, subject_id, payload)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(subject_id: int, db: AsyncSession = Depends(get_db)):
    await subject_service.delete_subject(db, subject_id)
