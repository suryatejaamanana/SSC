from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject
from app.repositories import subject_repository
from app.schemas.subject import SubjectCreate, SubjectUpdate

DUPLICATE_SUBJECT_DETAIL = "A subject with this name already exists"


async def create_subject(db: AsyncSession, payload: SubjectCreate) -> Subject:
    subject = Subject(name=payload.name, description=payload.description)
    db.add(subject)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_SUBJECT_DETAIL)
    await db.refresh(subject)
    return subject


async def list_subjects(db: AsyncSession) -> list[Subject]:
    return await subject_repository.list_all(db)


async def get_subject(db: AsyncSession, subject_id: int) -> Subject:
    subject = await subject_repository.get_by_id(db, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


async def update_subject(db: AsyncSession, subject_id: int, payload: SubjectUpdate) -> Subject:
    subject = await get_subject(db, subject_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_SUBJECT_DETAIL)
    await db.refresh(subject)
    return subject


async def delete_subject(db: AsyncSession, subject_id: int) -> None:
    subject = await get_subject(db, subject_id)
    try:
        await subject_repository.delete(db, subject)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject cannot be deleted while topics or questions still reference it",
        )
