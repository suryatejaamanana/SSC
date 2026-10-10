"""Unit tests for the require_role dependency itself.

get_current_user (cookie -> JWT -> DB lookup) is already exercised end-to-end
via /api/v1/auth/me in test_auth.py (tests 5 and 6). There is no admin-protected
business endpoint yet (that arrives with admin CRUD in a later phase), so these
tests call the dependency function directly rather than inventing a throwaway
route.
"""

import pytest
from fastapi import HTTPException

from app.auth.dependencies import require_role
from app.models.enums import UserRole
from app.models.user import User


def _make_user(role: UserRole) -> User:
    return User(id=1, name="Test", email="test@example.com", password_hash="x", role=role, is_active=True)


# 7. Student role authorization
async def test_require_role_rejects_wrong_role():
    dependency = require_role("admin")
    student = _make_user(UserRole.STUDENT)

    with pytest.raises(HTTPException) as exc_info:
        await dependency(current_user=student)

    assert exc_info.value.status_code == 403


# 8. Admin role authorization
async def test_require_role_allows_matching_role():
    dependency = require_role("admin")
    admin = _make_user(UserRole.ADMIN)

    result = await dependency(current_user=admin)

    assert result is admin
