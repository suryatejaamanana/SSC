from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attempt import Attempt
from app.models.attempt_answer import AttemptAnswer
from app.models.enums import AttemptStatus
from app.models.question import Question
from app.models.subject import Subject


async def get_for_attempt_and_question(
    db: AsyncSession, attempt_id: int, question_id: int
) -> AttemptAnswer | None:
    stmt = select(AttemptAnswer).where(
        AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_id == question_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_for_attempt_with_question(db: AsyncSession, attempt_id: int) -> list[AttemptAnswer]:
    """Eager-loads .question so the scoring loop can read correct_option /
    positive_marks / negative_marks without a lazy-load (which would fail
    outside the async session's awaited context)."""
    stmt = (
        select(AttemptAnswer)
        .options(selectinload(AttemptAnswer.question))
        .where(AttemptAnswer.attempt_id == attempt_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_section_performance_for_user(db: AsyncSession, user_id: int) -> list[Row]:
    """One row per subject the user has ever answered a published question
    for, across every completed (non in_progress) attempt regardless of
    type - full paper, section practice, or topic practice all count,
    since this is "how am I doing in Reasoning overall", not scoped to one
    attempt type. Each row: (subject_id, subject_name, total, correct,
    wrong, unanswered)."""
    stmt = (
        select(
            Subject.id,
            Subject.name,
            func.count(AttemptAnswer.id),
            func.count(AttemptAnswer.id).filter(AttemptAnswer.is_correct.is_(True)),
            func.count(AttemptAnswer.id).filter(AttemptAnswer.is_correct.is_(False)),
            func.count(AttemptAnswer.id).filter(AttemptAnswer.selected_option.is_(None)),
        )
        .select_from(AttemptAnswer)
        .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
        .join(Question, Question.id == AttemptAnswer.question_id)
        .join(Subject, Subject.id == Question.subject_id)
        .where(Attempt.user_id == user_id, Attempt.status != AttemptStatus.IN_PROGRESS)
        .group_by(Subject.id, Subject.name)
        .order_by(Subject.name)
    )
    result = await db.execute(stmt)
    return list(result.all())
