from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam
from app.repositories import exam_repository, question_repository
from app.schemas.exam import ExamCreate, ExamUpdate

DUPLICATE_EXAM_DETAIL = "An exam with this year/tier/shift already exists"


async def create_exam(db: AsyncSession, payload: ExamCreate, *, created_by: int) -> Exam:
    exam = Exam(
        year=payload.year,
        tier=payload.tier,
        shift=payload.shift,
        exam_date=payload.exam_date,
        duration_minutes=payload.duration_minutes,
        total_questions=payload.total_questions,
        total_marks=payload.total_marks,
        source_pdf_name=payload.source_pdf_name,
        created_by=created_by,
    )
    db.add(exam)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_EXAM_DETAIL)
    await db.refresh(exam)
    return exam


async def list_exams(db: AsyncSession) -> list[Exam]:
    return await exam_repository.list_all(db)


async def list_published_exams(db: AsyncSession) -> list[Exam]:
    """Student-facing catalog read - published exams only. Unlike the admin
    listing, there is no role restriction here beyond being an authenticated
    user; unpublished exams must never appear."""
    return await exam_repository.list_published(db)


async def get_published_exam(db: AsyncSession, exam_id: int) -> Exam:
    exam = await exam_repository.get_by_id(db, exam_id)
    if exam is None or not exam.is_published:
        # Treat "exists but unpublished" the same as "doesn't exist" - a
        # student has no legitimate reason to probe for draft exam ids.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


async def get_exam(db: AsyncSession, exam_id: int) -> Exam:
    exam = await exam_repository.get_by_id(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam


async def update_exam(db: AsyncSession, exam_id: int, payload: ExamUpdate) -> Exam:
    exam = await get_exam(db, exam_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_EXAM_DETAIL)
    await db.refresh(exam)
    return exam


async def delete_exam(db: AsyncSession, exam_id: int) -> None:
    exam = await get_exam(db, exam_id)
    try:
        await exam_repository.delete(db, exam)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam cannot be deleted while questions still reference it",
        )


async def publish_exam(db: AsyncSession, exam_id: int) -> Exam:
    """Validates and publishes an exam in one transaction.

    An exam may only be published once every question it declared (via
    total_questions/total_marks - the ground-truth values set at exam
    creation) is itself published. This reuses the same stored-expectation
    fields the Phase 1 design calls for validating PDF-import completeness,
    applied here to manually-entered exams too.
    """
    exam = await get_exam(db, exam_id)

    if exam.is_published:
        return exam  # idempotent - already published

    published_count, published_marks = await question_repository.count_published_for_exam(
        db, exam_id
    )

    errors: list[str] = []
    if published_count != exam.total_questions:
        errors.append(
            f"{published_count} of {exam.total_questions} required questions are published."
        )
    if published_marks != exam.total_marks:
        errors.append(
            f"Published questions total {published_marks} marks; exam expects {exam.total_marks}."
        )

    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors})

    exam.is_published = True
    await db.commit()
    await db.refresh(exam)
    return exam
