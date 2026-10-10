from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.deps import get_db
from app.schemas.topic import TopicCreate, TopicPublic, TopicUpdate
from app.services import topic_service

router = APIRouter(
    prefix="/admin/topics",
    tags=["admin:topics"],
    dependencies=[Depends(require_role("admin"))],
)


@router.post("", response_model=TopicPublic, status_code=status.HTTP_201_CREATED)
async def create_topic(payload: TopicCreate, db: AsyncSession = Depends(get_db)):
    return await topic_service.create_topic(db, payload)


@router.get("", response_model=list[TopicPublic])
async def list_topics(subject_id: int | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    return await topic_service.list_topics(db, subject_id=subject_id)


@router.get("/{topic_id}", response_model=TopicPublic)
async def get_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    return await topic_service.get_topic(db, topic_id)


@router.patch("/{topic_id}", response_model=TopicPublic)
async def update_topic(topic_id: int, payload: TopicUpdate, db: AsyncSession = Depends(get_db)):
    return await topic_service.update_topic(db, topic_id, payload)


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    await topic_service.delete_topic(db, topic_id)
