from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attempt_answer import AttemptAnswer
from app.models.attempt_question import AttemptQuestion
from app.models.question import Question


async def list_with_question_and_answer(db: AsyncSession, attempt_id: int) -> list[Row]:
    """One row per attempt_question: (AttemptQuestion, Question [with options
    eager-loaded], AttemptAnswer-or-None), ordered by the frozen snapshot
    order. A left join against attempt_answers is only defensive - every
    attempt_question has a matching attempt_answer created at the same time,
    but the join is written to tolerate it being missing regardless."""
    stmt = (
        select(AttemptQuestion, Question, AttemptAnswer)
        .join(Question, Question.id == AttemptQuestion.question_id)
        .outerjoin(
            AttemptAnswer,
            (AttemptAnswer.attempt_id == AttemptQuestion.attempt_id)
            & (AttemptAnswer.question_id == AttemptQuestion.question_id),
        )
        .options(selectinload(Question.options))
        .where(AttemptQuestion.attempt_id == attempt_id)
        .order_by(AttemptQuestion.order_index)
    )
    result = await db.execute(stmt)
    return list(result.all())
