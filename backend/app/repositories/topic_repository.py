from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import Topic


async def list_all(db: AsyncSession, *, subject_id: int | None = None) -> list[Topic]:
    stmt = select(Topic).order_by(Topic.subject_id, Topic.name)
    if subject_id is not None:
        stmt = stmt.where(Topic.subject_id == subject_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, topic_id: int) -> Topic | None:
    return await db.get(Topic, topic_id)


async def delete(db: AsyncSession, topic: Topic) -> None:
    await db.delete(topic)
    await db.flush()
