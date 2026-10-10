from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic
from app.repositories import subject_repository, topic_repository
from app.schemas.topic import TopicCreate, TopicUpdate

DUPLICATE_TOPIC_DETAIL = "A topic with this name already exists for this subject"


async def _ensure_subject_exists(db: AsyncSession, subject_id: int) -> None:
    subject = await subject_repository.get_by_id(db, subject_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="subject_id does not reference an existing subject",
        )


async def create_topic(db: AsyncSession, payload: TopicCreate) -> Topic:
    await _ensure_subject_exists(db, payload.subject_id)

    topic = Topic(subject_id=payload.subject_id, name=payload.name, description=payload.description)
    db.add(topic)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_TOPIC_DETAIL)
    await db.refresh(topic)
    return topic


async def list_topics(db: AsyncSession, *, subject_id: int | None = None) -> list[Topic]:
    return await topic_repository.list_all(db, subject_id=subject_id)


async def get_topic(db: AsyncSession, topic_id: int) -> Topic:
    topic = await topic_repository.get_by_id(db, topic_id)
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


async def update_topic(db: AsyncSession, topic_id: int, payload: TopicUpdate) -> Topic:
    topic = await get_topic(db, topic_id)

    data = payload.model_dump(exclude_unset=True)
    if "subject_id" in data:
        await _ensure_subject_exists(db, data["subject_id"])

    for field, value in data.items():
        setattr(topic, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE_TOPIC_DETAIL)
    await db.refresh(topic)
    return topic


async def delete_topic(db: AsyncSession, topic_id: int) -> None:
    topic = await get_topic(db, topic_id)
    try:
        await topic_repository.delete(db, topic)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Topic cannot be deleted while questions still reference it",
        )
