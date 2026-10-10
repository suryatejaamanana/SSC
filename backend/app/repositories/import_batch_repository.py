from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QuestionStatus
from app.models.import_batch import ImportBatch
from app.models.question import Question


async def get_by_id(db: AsyncSession, batch_id: int) -> ImportBatch | None:
    return await db.get(ImportBatch, batch_id)


async def list_all(db: AsyncSession) -> list[ImportBatch]:
    result = await db.execute(select(ImportBatch).order_by(ImportBatch.created_at.desc()))
    return list(result.scalars().all())


async def question_counts(db: AsyncSession, batch_id: int) -> tuple[int, int, int, int]:
    """Returns (total, pending_review, published, missing_correct_option)
    question counts for the batch. missing_correct_option counts questions
    the importer genuinely could not determine a correct answer for (never
    a guess) - these need admin attention before they can publish."""
    stmt = select(
        func.count(Question.id),
        func.count(Question.id).filter(Question.status == QuestionStatus.PENDING_REVIEW),
        func.count(Question.id).filter(Question.status == QuestionStatus.PUBLISHED),
        func.count(Question.id).filter(Question.correct_option.is_(None)),
    ).where(Question.import_batch_id == batch_id)
    result = await db.execute(stmt)
    total, pending, published, missing_correct = result.one()
    return total, pending, published, missing_correct
