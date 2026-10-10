from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import QuestionStatus
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.repositories import exam_repository, question_repository, subject_repository, topic_repository
from app.schemas.question import QuestionCreate, QuestionUpdate

VALID_LABELS = {"A", "B", "C", "D"}

DUPLICATE_QUESTION_DETAIL = "Question violates a uniqueness constraint (e.g. exam_id + question_number)"


def validate_question_for_publish(question: Question) -> list[str]:
    """The publish-readiness check. Deliberately NOT delegated to the
    database alone - the DB's CHECK constraint covers subject/correct_option,
    but the "exactly 4 options, A-D, no duplicates" rule is a cross-row count
    the database cannot express declaratively, so it is enforced here
    instead.

    topic_id is deliberately NOT required (Phase 9 final fix): topic
    classification doesn't happen at all for now, imported or manually
    entered.
    """
    errors: list[str] = []

    if not question.question_text or not question.question_text.strip():
        errors.append("Question text is required.")
    if question.subject_id is None:
        errors.append("Question must have a subject assigned.")
    if question.correct_option is None:
        errors.append("Question must have a correct option set.")

    labels = [opt.label for opt in question.options]
    if len(labels) != 4:
        errors.append(f"Exactly 4 options are required, found {len(labels)}.")
    else:
        if len(set(labels)) != len(labels):
            errors.append("Option labels must not contain duplicates.")
        if set(labels) != VALID_LABELS:
            errors.append("Option labels must be exactly A, B, C, and D.")

    for opt in question.options:
        if not (opt.text and opt.text.strip()) and not opt.image_url:
            errors.append(f"Option {opt.label} must have text or an image.")

    if question.positive_marks is None or question.positive_marks < 0:
        errors.append("positive_marks must be a non-negative value.")
    if question.negative_marks is None or question.negative_marks < 0:
        errors.append("negative_marks must be a non-negative value.")

    return errors


async def _resolve_subject_and_topic(
    db: AsyncSession, subject_id: int | None, topic_id: int | None
) -> tuple[int | None, int | None]:
    topic = None
    if topic_id is not None:
        topic = await topic_repository.get_by_id(db, topic_id)
        if topic is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="topic_id does not reference an existing topic",
            )

    if subject_id is not None:
        subject = await subject_repository.get_by_id(db, subject_id)
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="subject_id does not reference an existing subject",
            )
        if topic is not None and topic.subject_id != subject_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="topic does not belong to the given subject",
            )
    elif topic is not None:
        # subject_id omitted but a topic was given - backfill it from the
        # topic so the two FKs never end up inconsistent.
        subject_id = topic.subject_id

    return subject_id, topic_id


async def create_question(db: AsyncSession, payload: QuestionCreate) -> Question:
    if payload.exam_id is not None:
        exam = await exam_repository.get_by_id(db, payload.exam_id)
        if exam is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="exam_id does not reference an existing exam",
            )

    subject_id, topic_id = await _resolve_subject_and_topic(db, payload.subject_id, payload.topic_id)

    question = Question(
        exam_id=payload.exam_id,
        subject_id=subject_id,
        topic_id=topic_id,
        question_number=payload.question_number,
        question_text=payload.question_text,
        question_image_url=payload.question_image_url,
        correct_option=payload.correct_option,
        positive_marks=payload.positive_marks,
        negative_marks=payload.negative_marks,
        solution_text=payload.solution_text,
    )
    db.add(question)

    try:
        await db.flush()
        for opt in payload.options:
            db.add(
                QuestionOption(
                    question_id=question.id, label=opt.label, text=opt.text, image_url=opt.image_url
                )
            )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_QUESTION_DETAIL)

    return await question_repository.get_by_id(db, question.id)


async def list_questions(db: AsyncSession, **filters) -> list[Question]:
    return await question_repository.list_all(db, **filters)


async def get_question(db: AsyncSession, question_id: int) -> Question:
    question = await question_repository.get_by_id(db, question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


async def update_question(db: AsyncSession, question_id: int, payload: QuestionUpdate) -> Question:
    question = await get_question(db, question_id)

    data = payload.model_dump(exclude_unset=True, exclude={"options"})

    if "exam_id" in data and data["exam_id"] is not None:
        exam = await exam_repository.get_by_id(db, data["exam_id"])
        if exam is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="exam_id does not reference an existing exam",
            )

    if "subject_id" in data or "topic_id" in data:
        new_subject_id = data.get("subject_id", question.subject_id)
        new_topic_id = data.get("topic_id", question.topic_id)
        new_subject_id, new_topic_id = await _resolve_subject_and_topic(db, new_subject_id, new_topic_id)
        data["subject_id"] = new_subject_id
        data["topic_id"] = new_topic_id

    if "status" in data:
        data["status"] = QuestionStatus(data["status"])

    for field, value in data.items():
        setattr(question, field, value)

    if payload.options is not None:
        await question_repository.replace_options(
            db, question, [opt.model_dump() for opt in payload.options]
        )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_QUESTION_DETAIL)

    return await question_repository.get_by_id(db, question_id)


async def delete_question(db: AsyncSession, question_id: int) -> None:
    question = await get_question(db, question_id)
    try:
        await question_repository.delete(db, question)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question cannot be deleted while it is referenced elsewhere",
        )


async def publish_question(db: AsyncSession, question_id: int) -> Question:
    question = await get_question(db, question_id)

    errors = validate_question_for_publish(question)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors})

    question.status = QuestionStatus.PUBLISHED
    await db.commit()
    return await question_repository.get_by_id(db, question_id)
