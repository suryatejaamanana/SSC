from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import Exam


async def list_all(db: AsyncSession) -> list[Exam]:
    result = await db.execute(select(Exam).order_by(Exam.year.desc(), Exam.tier, Exam.shift))
    return list(result.scalars().all())


async def list_published(db: AsyncSession) -> list[Exam]:
    stmt = (
        select(Exam)
        .where(Exam.is_published.is_(True))
        .order_by(Exam.year.desc(), Exam.tier, Exam.shift)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, exam_id: int) -> Exam | None:
    return await db.get(Exam, exam_id)


async def get_by_year_tier_shift(db: AsyncSession, year: int, tier: str, shift: int) -> Exam | None:
    stmt = select(Exam).where(Exam.year == year, Exam.tier == tier, Exam.shift == shift)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete(db: AsyncSession, exam: Exam) -> None:
    await db.delete(exam)
    await db.flush()
