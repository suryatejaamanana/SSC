from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories import user_repository
from app.schemas.auth import UserUpdate

SELF_MODIFICATION_DETAIL = "You cannot change your own role or active status"


async def list_users(db: AsyncSession) -> list[User]:
    return await user_repository.list_all(db)


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


async def update_user(db: AsyncSession, user_id: int, payload: UserUpdate, *, current_user_id: int) -> User:
    # An admin locking out their own account (demoting themselves, or
    # deactivating themselves) with no other admin able to undo it is an
    # easy mistake with no recovery path in this app (no superuser bypass),
    # so it's blocked outright rather than just warned about.
    if user_id == current_user_id and payload.model_dump(exclude_unset=True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=SELF_MODIFICATION_DETAIL)

    user = await get_user(db, user_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user
