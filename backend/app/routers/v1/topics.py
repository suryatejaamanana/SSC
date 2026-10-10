from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.deps import get_db
from app.schemas.topic import TopicPublic
from app.services import topic_service

router = APIRouter(prefix="/topics", tags=["topics"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TopicPublic])
async def list_topics(subject_id: int | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    return await topic_service.list_topics(db, subject_id=subject_id)
