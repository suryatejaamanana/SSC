from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.deps import get_db
from app.models.enums import AttemptStatus, AttemptType
from app.models.user import User
from app.schemas.attempt import (
    AnswerPublic,
    AnswerSubmit,
    AttemptCreate,
    AttemptHistoryPage,
    AttemptHistorySummary,
    AttemptPublic,
    AttemptResult,
    QuestionForAttempt,
    ReviewItem,
    SectionPerformance,
    SectionPracticeAttemptCreate,
    TopicPracticeAttemptCreate,
)
from app.services import attempt_service

router = APIRouter(
    prefix="/attempts",
    tags=["attempts"],
    dependencies=[Depends(require_role("student"))],
)


@router.post("", response_model=AttemptPublic, status_code=status.HTTP_201_CREATED)
async def create_attempt(
    payload: AttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await attempt_service.create_attempt(db, user_id=current_user.id, exam_id=payload.exam_id)


@router.post("/topic-practice", response_model=AttemptPublic, status_code=status.HTTP_201_CREATED)
async def create_topic_practice_attempt(
    payload: TopicPracticeAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await attempt_service.create_topic_practice_attempt(
        db,
        user_id=current_user.id,
        topic_id=payload.topic_id,
        question_count=payload.question_count,
    )


@router.post("/section-practice", response_model=AttemptPublic, status_code=status.HTTP_201_CREATED)
async def create_section_practice_attempt(
    payload: SectionPracticeAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await attempt_service.create_section_practice_attempt(
        db,
        user_id=current_user.id,
        exam_id=payload.exam_id,
        subject_id=payload.subject_id,
    )


@router.get("/history", response_model=AttemptHistoryPage)
async def get_attempt_history(
    attempt_type: AttemptType | None = Query(default=None),
    status_filter: AttemptStatus | None = Query(default=None, alias="status"),
    exam_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await attempt_service.list_attempt_history(
        db,
        current_user.id,
        attempt_type=attempt_type,
        attempt_status=status_filter,
        exam_id=exam_id,
        topic_id=topic_id,
        limit=limit,
        offset=offset,
    )
    return AttemptHistoryPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/history/summary", response_model=AttemptHistorySummary)
async def get_attempt_history_summary(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_attempt_history_summary(db, current_user.id)


@router.get("/history/section-performance", response_model=list[SectionPerformance])
async def get_section_performance(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_section_performance(db, current_user.id)


# IMPORTANT: the parameterized routes below must stay registered AFTER the
# static "/history" routes above - Starlette matches routes in registration
# order using a plain string converter for "{attempt_id}", so "history"
# would otherwise match it first and fail type-validation with a 422
# instead of ever reaching the routes above.


@router.get("/{attempt_id}", response_model=AttemptPublic)
async def get_attempt(
    attempt_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_attempt(db, attempt_id, current_user.id)


@router.get("/{attempt_id}/questions", response_model=list[QuestionForAttempt])
async def get_attempt_questions(
    attempt_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_attempt_questions(db, attempt_id, current_user.id)


@router.post("/{attempt_id}/answers", response_model=AnswerPublic)
async def save_answer(
    attempt_id: int,
    payload: AnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await attempt_service.save_answer(db, attempt_id, current_user.id, payload)


@router.post("/{attempt_id}/submit", response_model=AttemptPublic)
async def submit_attempt(
    attempt_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.submit_attempt(db, attempt_id, current_user.id)


@router.get("/{attempt_id}/result", response_model=AttemptResult)
async def get_result(
    attempt_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_result(db, attempt_id, current_user.id)


@router.get("/{attempt_id}/review", response_model=list[ReviewItem])
async def get_review(
    attempt_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await attempt_service.get_review(db, attempt_id, current_user.id)
