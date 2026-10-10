import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.cookies import ACCESS_TOKEN_COOKIE
from app.core.security import decode_access_token
from app.db.deps import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import user_repository


def _not_authenticated() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise _not_authenticated()

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise _not_authenticated()

    if payload.get("type") != "access":
        raise _not_authenticated()

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _not_authenticated()

    # Re-fetch from the DB rather than trusting the JWT's role claim, so a
    # role change or account deactivation takes effect immediately instead of
    # waiting for the short-lived access token to expire.
    user = await user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise _not_authenticated()

    return user


def require_role(role: UserRole | str):
    role_value = role.value if isinstance(role, UserRole) else role

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value != role_value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return dependency
