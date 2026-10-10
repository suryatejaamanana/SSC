from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.deps import get_db
from app.models.user import User
from app.schemas.auth import UserPublic, UserUpdate
from app.services import user_service

router = APIRouter(
    prefix="/admin/users",
    tags=["admin:users"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("", response_model=list[UserPublic])
async def list_users(db: AsyncSession = Depends(get_db)):
    return await user_service.list_users(db)


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await user_service.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_service.update_user(db, user_id, payload, current_user_id=current_user.id)
