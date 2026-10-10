import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attempt import Attempt
from app.models.attempt_answer import AttemptAnswer
from app.models.attempt_question import AttemptQuestion
from app.models.enums import AttemptStatus, AttemptType, QuestionStatus
from app.models.question import Question
from app.repositories import (
    attempt_answer_repository,
    attempt_question_repository,
    attempt_repository,
    exam_repository,
    question_repository,
    subject_repository,
    topic_repository,
)
from app.schemas.attempt import (
    AnswerSubmit,
    AttemptHistoryItem,
    AttemptHistorySummary,
    AttemptResult,
    OptionForAttempt,
    QuestionForAttempt,
    ReviewItem,
    SectionPerformance,
)

ATTEMPT_NOT_FOUND_DETAIL = "Attempt not found"

# Topic practice has no exam to inherit a duration from, so it uses a fixed,
# server-controlled time budget per question instead of trusting any
# client-supplied value.
TOPIC_PRACTICE_SECONDS_PER_QUESTION = 90

# Section practice (a 25-question slice of one shift's paper, scoped to a
# single section/subject) deliberately does NOT derive its duration from the
# parent exam's duration via a formula (e.g. duration/4) - that would make
# the practice timer an accidental side effect of exam authoring rather than
# a real product decision. A single named constant instead, easy to tune
# later without touching the exam model or the attempt-creation logic.
SECTION_PRACTICE_DURATION_MINUTES = 15


async def _snapshot_questions(db: AsyncSession, attempt_id: int, questions: list[Question]) -> None:
    """Freezes the given questions (in the given order) as this attempt's
    question set, and pre-creates one attempt_answer row per question so
    /answers is always a plain UPDATE. Shared by both full-paper and
    topic-practice attempt creation."""
    for order_index, question in enumerate(questions):
        db.add(
            AttemptQuestion(attempt_id=attempt_id, question_id=question.id, order_index=order_index)
        )
        db.add(AttemptAnswer(attempt_id=attempt_id, question_id=question.id))


async def create_attempt(db: AsyncSession, *, user_id: int, exam_id: int) -> Attempt:
    exam = await exam_repository.get_by_id(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if not exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Exam is not published"
        )

    questions = await question_repository.list_all(
        db, exam_id=exam_id, status=QuestionStatus.PUBLISHED
    )
    # Stable, deterministic order: by the paper's own question_number, with
    # the row id as a tiebreaker for any (unexpected) nulls.
    questions.sort(key=lambda q: (q.question_number is None, q.question_number or 0, q.id))

    now = datetime.now(timezone.utc)
    attempt = Attempt(
        user_id=user_id,
        exam_id=exam_id,
        attempt_type=AttemptType.FULL_PAPER,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now,
        expires_at=now + timedelta(minutes=exam.duration_minutes),
    )
    db.add(attempt)
    await db.flush()  # populate attempt.id for the snapshot rows below

    await _snapshot_questions(db, attempt.id, questions)

    await db.commit()
    await db.refresh(attempt)
    return attempt


async def create_topic_practice_attempt(
    db: AsyncSession, *, user_id: int, topic_id: int, question_count: int
) -> Attempt:
    topic = await topic_repository.get_by_id(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    available = await question_repository.list_all(
        db, topic_id=topic_id, status=QuestionStatus.PUBLISHED
    )
    if not available:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This topic has no published questions available for practice",
        )
    if question_count > len(available):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Only {len(available)} published question(s) are available for this topic; "
                f"requested {question_count}."
            ),
        )

    selected_questions = random.sample(available, question_count)

    now = datetime.now(timezone.utc)
    attempt = Attempt(
        user_id=user_id,
        topic_id=topic_id,
        attempt_type=AttemptType.TOPIC_PRACTICE,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now,
        expires_at=now + timedelta(seconds=question_count * TOPIC_PRACTICE_SECONDS_PER_QUESTION),
    )
    db.add(attempt)
    await db.flush()

    await _snapshot_questions(db, attempt.id, selected_questions)

    await db.commit()
    await db.refresh(attempt)
    return attempt


async def create_section_practice_attempt(
    db: AsyncSession, *, user_id: int, exam_id: int, subject_id: int
) -> Attempt:
    """25-question slice of a single published shift exam, scoped to one
    section (subject) - distinct from create_topic_practice_attempt, which
    draws a configurable-count random sample across ALL exams for a topic.
    This always takes every published question the exam has for that
    subject, in question_number order, mirroring create_attempt's full-paper
    ordering."""
    exam = await exam_repository.get_by_id(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if not exam.is_published:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Exam is not published"
        )

    subject = await subject_repository.get_by_id(db, subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    questions = await question_repository.list_all(
        db, exam_id=exam_id, subject_id=subject_id, status=QuestionStatus.PUBLISHED
    )
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This exam has no published questions in that section yet",
        )
    questions.sort(key=lambda q: (q.question_number is None, q.question_number or 0, q.id))

    now = datetime.now(timezone.utc)
    attempt = Attempt(
        user_id=user_id,
        exam_id=exam_id,
        subject_id=subject_id,
        attempt_type=AttemptType.SECTION_PRACTICE,
        status=AttemptStatus.IN_PROGRESS,
        started_at=now,
        expires_at=now + timedelta(minutes=SECTION_PRACTICE_DURATION_MINUTES),
    )
    db.add(attempt)
    await db.flush()

    await _snapshot_questions(db, attempt.id, questions)

    await db.commit()
    await db.refresh(attempt)
    return attempt


async def _get_owned_attempt(db: AsyncSession, attempt_id: int, user_id: int) -> Attempt:
    attempt = await attempt_repository.get_by_id(db, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        # 404, not 403: don't reveal that an attempt belonging to someone
        # else even exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ATTEMPT_NOT_FOUND_DETAIL)
    return attempt


async def _score_and_finalize(
    db: AsyncSession, attempt: Attempt, *, new_status: AttemptStatus, submitted_at: datetime
) -> None:
    answers = await attempt_answer_repository.list_for_attempt_with_question(db, attempt.id)

    correct_count = 0
    wrong_count = 0
    unanswered_count = 0
    score = Decimal("0.00")

    for answer in answers:
        if answer.selected_option is None:
            unanswered_count += 1
            continue

        question = answer.question
        if answer.selected_option == question.correct_option:
            answer.is_correct = True
            correct_count += 1
            score += question.positive_marks
        else:
            answer.is_correct = False
            wrong_count += 1
            score -= question.negative_marks

    attempt.status = new_status
    attempt.submitted_at = submitted_at
    attempt.score = score
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.unanswered_count = unanswered_count

    await db.commit()


async def _get_current_attempt(db: AsyncSession, attempt_id: int, user_id: int) -> Attempt:
    """Ownership-checked fetch that also lazily finalizes the attempt as
    'expired' if its timer has already run out but it is still in_progress -
    every read/write path below goes through this so expiry is enforced no
    matter which endpoint the student happens to call next."""
    attempt = await _get_owned_attempt(db, attempt_id, user_id)

    if attempt.status == AttemptStatus.IN_PROGRESS and attempt.expires_at <= datetime.now(timezone.utc):
        # Re-fetch under a row lock before finalizing, in case a concurrent
        # manual submit got there first while we were deciding to expire it.
        locked = await attempt_repository.get_by_id_for_update(db, attempt_id)
        if locked.status == AttemptStatus.IN_PROGRESS and locked.expires_at <= datetime.now(timezone.utc):
            await _score_and_finalize(
                db, locked, new_status=AttemptStatus.EXPIRED, submitted_at=locked.expires_at
            )
        return locked

    return attempt


async def get_attempt(db: AsyncSession, attempt_id: int, user_id: int) -> Attempt:
    return await _get_current_attempt(db, attempt_id, user_id)


async def get_attempt_questions(
    db: AsyncSession, attempt_id: int, user_id: int
) -> list[QuestionForAttempt]:
    await _get_current_attempt(db, attempt_id, user_id)

    rows = await attempt_question_repository.list_with_question_and_answer(db, attempt_id)

    items: list[QuestionForAttempt] = []
    for attempt_question, question, answer in rows:
        items.append(
            QuestionForAttempt(
                question_id=question.id,
                order_index=attempt_question.order_index,
                question_number=question.question_number,
                question_text=question.question_text,
                question_image_url=question.question_image_url,
                passage_text=question.passage_text,
                positive_marks=question.positive_marks,
                negative_marks=question.negative_marks,
                options=[
                    OptionForAttempt(label=opt.label, text=opt.text, image_url=opt.image_url)
                    for opt in question.options
                ],
                selected_option=answer.selected_option if answer else None,
                marked_for_review=answer.marked_for_review if answer else False,
            )
        )
    return items


async def save_answer(
    db: AsyncSession, attempt_id: int, user_id: int, payload: AnswerSubmit
) -> AttemptAnswer:
    attempt = await _get_current_attempt(db, attempt_id, user_id)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt is no longer in progress"
        )

    answer = await attempt_answer_repository.get_for_attempt_and_question(
        db, attempt_id, payload.question_id
    )
    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This question is not part of this attempt",
        )

    answer.selected_option = payload.selected_option
    answer.marked_for_review = payload.marked_for_review
    answer.time_spent_seconds = payload.time_spent_seconds
    answer.answered_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(answer)
    return answer


async def submit_attempt(db: AsyncSession, attempt_id: int, user_id: int) -> Attempt:
    # Locks the row for the whole decision, so a second concurrent submit
    # call blocks until this one commits, then sees status != in_progress
    # and simply returns the already-computed result - idempotent by
    # construction, not by a special-cased "already submitted" branch.
    attempt = await attempt_repository.get_by_id_for_update(db, attempt_id)
    if attempt is None or attempt.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ATTEMPT_NOT_FOUND_DETAIL)

    if attempt.status != AttemptStatus.IN_PROGRESS:
        return attempt

    now = datetime.now(timezone.utc)
    if attempt.expires_at <= now:
        # The deadline had already passed by the time this request arrived -
        # record it as expired, not submitted, and score against the actual
        # deadline rather than whenever the request happened to land.
        await _score_and_finalize(
            db, attempt, new_status=AttemptStatus.EXPIRED, submitted_at=attempt.expires_at
        )
    else:
        await _score_and_finalize(db, attempt, new_status=AttemptStatus.SUBMITTED, submitted_at=now)

    return attempt


async def get_result(db: AsyncSession, attempt_id: int, user_id: int) -> AttemptResult:
    attempt = await _get_current_attempt(db, attempt_id, user_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt has not been submitted yet"
        )

    total_questions = attempt.correct_count + attempt.wrong_count + attempt.unanswered_count
    attempted_count = attempt.correct_count + attempt.wrong_count
    accuracy = round((attempt.correct_count / attempted_count) * 100, 2) if attempted_count else 0.0
    time_taken_seconds = int((attempt.submitted_at - attempt.started_at).total_seconds())

    return AttemptResult(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status.value,
        total_questions=total_questions,
        attempted_count=attempted_count,
        correct_count=attempt.correct_count,
        wrong_count=attempt.wrong_count,
        unanswered_count=attempt.unanswered_count,
        score=attempt.score,
        accuracy=accuracy,
        time_taken_seconds=time_taken_seconds,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
    )


async def get_review(db: AsyncSession, attempt_id: int, user_id: int) -> list[ReviewItem]:
    attempt = await _get_current_attempt(db, attempt_id, user_id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt has not been submitted yet"
        )

    rows = await attempt_question_repository.list_with_question_and_answer(db, attempt_id)

    items: list[ReviewItem] = []
    for attempt_question, question, answer in rows:
        items.append(
            ReviewItem(
                question_id=question.id,
                order_index=attempt_question.order_index,
                question_number=question.question_number,
                question_text=question.question_text,
                question_image_url=question.question_image_url,
                passage_text=question.passage_text,
                options=[
                    OptionForAttempt(label=opt.label, text=opt.text, image_url=opt.image_url)
                    for opt in question.options
                ],
                selected_option=answer.selected_option if answer else None,
                correct_option=question.correct_option,
                is_correct=answer.is_correct if answer else None,
                solution_text=question.solution_text,
            )
        )
    return items


async def list_attempt_history(
    db: AsyncSession,
    user_id: int,
    *,
    attempt_type: AttemptType | None = None,
    attempt_status: AttemptStatus | None = None,
    exam_id: int | None = None,
    topic_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AttemptHistoryItem], int]:
    rows, total = await attempt_repository.list_for_user(
        db,
        user_id,
        attempt_type=attempt_type,
        status=attempt_status,
        exam_id=exam_id,
        topic_id=topic_id,
        limit=limit,
        offset=offset,
    )

    items: list[AttemptHistoryItem] = []
    for attempt, exam, topic, subject, topic_subject in rows:
        items.append(
            AttemptHistoryItem(
                attempt_id=attempt.id,
                attempt_type=attempt.attempt_type,
                status=attempt.status,
                exam_id=attempt.exam_id,
                exam_year=exam.year if exam else None,
                exam_tier=exam.tier if exam else None,
                exam_shift=exam.shift if exam else None,
                topic_id=attempt.topic_id,
                topic_name=topic.name if topic else None,
                subject_name=(subject or topic_subject).name if (subject or topic_subject) else None,
                started_at=attempt.started_at,
                submitted_at=attempt.submitted_at,
                score=attempt.score,
                correct_count=attempt.correct_count,
                wrong_count=attempt.wrong_count,
                unanswered_count=attempt.unanswered_count,
            )
        )
    return items, total


async def get_attempt_history_summary(db: AsyncSession, user_id: int) -> AttemptHistorySummary:
    total_attempts, total_correct, total_wrong, total_unanswered, average_score, total_time_seconds = (
        await attempt_repository.get_summary_for_user(db, user_id)
    )

    total_questions = total_correct + total_wrong + total_unanswered
    attempted = total_correct + total_wrong
    accuracy = round((total_correct / attempted) * 100, 2) if attempted else 0.0

    return AttemptHistorySummary(
        total_attempts=total_attempts,
        total_questions=total_questions,
        total_correct=total_correct,
        total_wrong=total_wrong,
        total_unanswered=total_unanswered,
        average_score=Decimal(str(average_score)).quantize(Decimal("0.01")),
        accuracy=accuracy,
        total_time_seconds=int(total_time_seconds),
    )


async def get_section_performance(db: AsyncSession, user_id: int) -> list[SectionPerformance]:
    rows = await attempt_answer_repository.get_section_performance_for_user(db, user_id)

    items: list[SectionPerformance] = []
    for subject_id, subject_name, total, correct, wrong, unanswered in rows:
        attempted = correct + wrong
        accuracy = round((correct / attempted) * 100, 2) if attempted else 0.0
        items.append(
            SectionPerformance(
                subject_id=subject_id,
                subject_name=subject_name,
                total_questions=total,
                correct_count=correct,
                wrong_count=wrong,
                unanswered_count=unanswered,
                accuracy=accuracy,
            )
        )
    return items
