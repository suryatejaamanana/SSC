from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subject import Subject


async def list_all(db: AsyncSession) -> list[Subject]:
    result = await db.execute(select(Subject).order_by(Subject.name))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, subject_id: int) -> Subject | None:
    return await db.get(Subject, subject_id)


async def get_by_name(db: AsyncSession, name: str) -> Subject | None:
    result = await db.execute(select(Subject).where(Subject.name == name))
    return result.scalar_one_or_none()


async def get_or_create_by_name(db: AsyncSession, name: str) -> Subject:
    """Idempotent get-or-create, used by PDF import to auto-assign the 4
    canonical section subjects without requiring an admin to have
    pre-created them. Flushes (not commits) so the caller controls the
    transaction boundary for the rest of the import."""
    subject = await get_by_name(db, name)
    if subject is not None:
        return subject
    subject = Subject(name=name)
    db.add(subject)
    await db.flush()
    return subject


async def delete(db: AsyncSession, subject: Subject) -> None:
    await db.delete(subject)
    await db.flush()
