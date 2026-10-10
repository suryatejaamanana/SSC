from sqlalchemy import func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.attempt import Attempt
from app.models.enums import AttemptStatus, AttemptType
from app.models.exam import Exam
from app.models.subject import Subject
from app.models.topic import Topic

TopicSubject = aliased(Subject)


async def get_by_id(db: AsyncSession, attempt_id: int) -> Attempt | None:
    return await db.get(Attempt, attempt_id)


async def get_by_id_for_update(db: AsyncSession, attempt_id: int) -> Attempt | None:
    """Locks the row (SELECT ... FOR UPDATE) for the duration of the current
    transaction - used by submit and by the lazy-expiry finalizer so two
    concurrent requests finalizing the same attempt (e.g. a manual submit
    racing an auto-expire check) serialize instead of double-scoring it."""
    stmt = select(Attempt).where(Attempt.id == attempt_id).with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _history_filters(
    user_id: int,
    *,
    attempt_type: AttemptType | None,
    status: AttemptStatus | None,
    exam_id: int | None,
    topic_id: int | None,
) -> list:
    # The user_id filter is always present and never comes from anywhere but
    # the authenticated caller's own id - there is no code path by which
    # this query can return another user's rows.
    conditions = [Attempt.user_id == user_id]
    if attempt_type is not None:
        conditions.append(Attempt.attempt_type == attempt_type)
    if status is not None:
        conditions.append(Attempt.status == status)
    if exam_id is not None:
        conditions.append(Attempt.exam_id == exam_id)
    if topic_id is not None:
        conditions.append(Attempt.topic_id == topic_id)
    return conditions


async def list_for_user(
    db: AsyncSession,
    user_id: int,
    *,
    attempt_type: AttemptType | None = None,
    status: AttemptStatus | None = None,
    exam_id: int | None = None,
    topic_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Row], int]:
    conditions = _history_filters(
        user_id, attempt_type=attempt_type, status=status, exam_id=exam_id, topic_id=topic_id
    )

    total = (
        await db.execute(select(func.count()).select_from(Attempt).where(*conditions))
    ).scalar_one()

    # Subject is joined two ways: directly (section_practice attempts carry
    # their own subject_id) and via Topic (topic_practice attempts don't) -
    # exactly one of the two will be non-null for any given row, and the
    # service layer picks whichever is present.
    rows_stmt = (
        select(Attempt, Exam, Topic, Subject, TopicSubject)
        .outerjoin(Exam, Exam.id == Attempt.exam_id)
        .outerjoin(Topic, Topic.id == Attempt.topic_id)
        .outerjoin(Subject, Subject.id == Attempt.subject_id)
        .outerjoin(TopicSubject, TopicSubject.id == Topic.subject_id)
        .where(*conditions)
        .order_by(Attempt.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(rows_stmt)).all()

    return list(rows), total


async def get_summary_for_user(db: AsyncSession, user_id: int) -> Row:
    """Aggregates over the user's completed attempts only (status != in_progress)
    - the Phase-1 CHECK constraint guarantees score/counts (and, for this
    set, submitted_at) are non-null for every row this matches."""
    time_taken = func.extract("epoch", Attempt.submitted_at - Attempt.started_at)
    stmt = select(
        func.count(Attempt.id),
        func.coalesce(func.sum(Attempt.correct_count), 0),
        func.coalesce(func.sum(Attempt.wrong_count), 0),
        func.coalesce(func.sum(Attempt.unanswered_count), 0),
        func.coalesce(func.avg(Attempt.score), 0),
        func.coalesce(func.sum(time_taken), 0),
    ).where(Attempt.user_id == user_id, Attempt.status != AttemptStatus.IN_PROGRESS)
    result = await db.execute(stmt)
    return result.one()
