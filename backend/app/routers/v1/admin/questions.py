from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db.deps import get_db
from app.models.enums import QuestionStatus
from app.schemas.question import QuestionCreate, QuestionPublic, QuestionUpdate
from app.services import question_service

router = APIRouter(
    prefix="/admin/questions",
    tags=["admin:questions"],
    dependencies=[Depends(require_role("admin"))],
)


@router.post("", response_model=QuestionPublic, status_code=status.HTTP_201_CREATED)
async def create_question(payload: QuestionCreate, db: AsyncSession = Depends(get_db)):
    return await question_service.create_question(db, payload)


@router.get("", response_model=list[QuestionPublic])
async def list_questions(
    exam_id: int | None = Query(default=None),
    subject_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    status_filter: QuestionStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await question_service.list_questions(
        db, exam_id=exam_id, subject_id=subject_id, topic_id=topic_id, status=status_filter
    )


@router.get("/{question_id}", response_model=QuestionPublic)
async def get_question(question_id: int, db: AsyncSession = Depends(get_db)):
    return await question_service.get_question(db, question_id)


@router.patch("/{question_id}", response_model=QuestionPublic)
async def update_question(question_id: int, payload: QuestionUpdate, db: AsyncSession = Depends(get_db)):
    return await question_service.update_question(db, question_id, payload)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: int, db: AsyncSession = Depends(get_db)):
    await question_service.delete_question(db, question_id)


@router.post("/{question_id}/publish", response_model=QuestionPublic)
async def publish_question(question_id: int, db: AsyncSession = Depends(get_db)):
    return await question_service.publish_question(db, question_id)
