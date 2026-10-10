from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import QuestionStatus
from app.models.question import Question
from app.models.question_option import QuestionOption


async def image_url_belongs_to_published_question(db: AsyncSession, url: str) -> bool:
    """True if `url` is the question_image_url of a published question, or
    the image_url of one of a published question's options. Used to gate
    the authenticated media route so a non-admin can't view a draft/
    pending_review/archived question's figure just by guessing its
    (predictably-named) image path before the question is actually
    published."""
    stem_stmt = select(Question.id).where(
        Question.question_image_url == url, Question.status == QuestionStatus.PUBLISHED
    )
    if (await db.execute(stem_stmt)).first() is not None:
        return True

    option_stmt = (
        select(QuestionOption.id)
        .join(Question, Question.id == QuestionOption.question_id)
        .where(QuestionOption.image_url == url, Question.status == QuestionStatus.PUBLISHED)
    )
    return (await db.execute(option_stmt)).first() is not None


async def get_by_id(db: AsyncSession, question_id: int) -> Question | None:
    stmt = (
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.id == question_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_all(
    db: AsyncSession,
    *,
    exam_id: int | None = None,
    subject_id: int | None = None,
    topic_id: int | None = None,
    status: QuestionStatus | None = None,
    import_batch_id: int | None = None,
) -> list[Question]:
    stmt = select(Question).options(selectinload(Question.options)).order_by(Question.id)
    if exam_id is not None:
        stmt = stmt.where(Question.exam_id == exam_id)
    if subject_id is not None:
        stmt = stmt.where(Question.subject_id == subject_id)
    if topic_id is not None:
        stmt = stmt.where(Question.topic_id == topic_id)
    if status is not None:
        stmt = stmt.where(Question.status == status)
    if import_batch_id is not None:
        stmt = stmt.where(Question.import_batch_id == import_batch_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete(db: AsyncSession, question: Question) -> None:
    await db.delete(question)
    await db.flush()


async def replace_options(db: AsyncSession, question: Question, options: list[dict]) -> None:
    """Deletes all existing options for the question and inserts the given set."""
    for existing in list(question.options):
        await db.delete(existing)
    await db.flush()
    for opt in options:
        db.add(QuestionOption(question_id=question.id, **opt))
    await db.flush()


async def count_published_for_exam(db: AsyncSession, exam_id: int) -> tuple[int, Decimal]:
    stmt = select(
        func.count(Question.id), func.coalesce(func.sum(Question.positive_marks), 0)
    ).where(Question.exam_id == exam_id, Question.status == QuestionStatus.PUBLISHED)
    result = await db.execute(stmt)
    count, total_marks = result.one()
    return count, Decimal(total_marks)
