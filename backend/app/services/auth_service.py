from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import refresh_token_repository, user_repository
from app.schemas.auth import LoginRequest, RegisterRequest

settings = get_settings()

INVALID_CREDENTIALS_DETAIL = "Invalid email or password"
INVALID_REFRESH_TOKEN_DETAIL = "Invalid refresh token"

# A precomputed hash with no matching account, used so a login attempt against
# a nonexistent email still runs exactly one bcrypt verification - the same
# cost as a real account - instead of returning early and leaking which
# emails are registered via a response-time side channel.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-account-password")


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    # Public registration always creates a student account. Admin accounts
    # are never self-service - that's deliberate, not an oversight.
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.STUDENT,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    await db.refresh(user)
    return user


async def _issue_tokens(db: AsyncSession, user: User) -> tuple[str, str]:
    access_token = create_access_token(user.id, user.role.value)
    raw_refresh_token = generate_refresh_token()
    await refresh_token_repository.create(
        db,
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    return access_token, raw_refresh_token


async def login_user(db: AsyncSession, payload: LoginRequest) -> tuple[User, str, str]:
    user = await user_repository.get_by_email(db, payload.email)
    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, password_hash)

    if user is None or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS_DETAIL
        )

    user.last_login_at = datetime.now(timezone.utc)
    access_token, raw_refresh_token = await _issue_tokens(db, user)
    await db.commit()
    await db.refresh(user)
    return user, access_token, raw_refresh_token


async def refresh_tokens(db: AsyncSession, raw_refresh_token: str) -> tuple[str, str]:
    token_row = await refresh_token_repository.get_by_hash(
        db, hash_refresh_token(raw_refresh_token)
    )

    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH_TOKEN_DETAIL
        )

    if token_row.revoked_at is not None:
        # Reuse of an already-rotated (or logged-out) refresh token is a
        # signal of possible theft. Revoke every other active token for this
        # user as a precaution, then reject this request.
        await refresh_token_repository.revoke_all_for_user(db, token_row.user_id)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH_TOKEN_DETAIL
        )

    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH_TOKEN_DETAIL
        )

    user = await user_repository.get_by_id(db, token_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_REFRESH_TOKEN_DETAIL
        )

    await refresh_token_repository.revoke(db, token_row)
    access_token, new_raw_refresh_token = await _issue_tokens(db, user)
    await db.commit()
    return access_token, new_raw_refresh_token


async def logout_user(db: AsyncSession, raw_refresh_token: str) -> None:
    token_row = await refresh_token_repository.get_by_hash(
        db, hash_refresh_token(raw_refresh_token)
    )
    if token_row is not None and token_row.revoked_at is None:
        await refresh_token_repository.revoke(db, token_row)
        await db.commit()
