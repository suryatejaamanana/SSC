import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

ALL_TABLES = (
    "attempt_answers, attempt_questions, attempts, import_batches, "
    "question_options, questions, exams, topics, subjects, "
    "refresh_tokens, users"
)


async def _truncate() -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {ALL_TABLES} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    await _truncate()
    yield
    await _truncate()
    # pytest-asyncio gives each test function its own event loop by default,
    # but the engine's asyncpg connection pool is a module-level singleton
    # created in whichever loop first used it. Dispose it after every test so
    # the next test opens fresh connections in ITS loop instead of reusing
    # connections bound to a now-closed one.
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def student_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={"name": "Student", "email": "student@example.com", "password": "correct-password-1"},
        )
        await ac.post(
            "/api/v1/auth/login",
            json={"email": "student@example.com", "password": "correct-password-1"},
        )
        yield ac


@pytest_asyncio.fixture
async def other_student_client():
    """A second, distinct student - used to verify ownership checks (another
    student's requests against someone else's attempt must 404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={
                "name": "Other Student",
                "email": "other-student@example.com",
                "password": "correct-password-1",
            },
        )
        await ac.post(
            "/api/v1/auth/login",
            json={"email": "other-student@example.com", "password": "correct-password-1"},
        )
        yield ac


@pytest_asyncio.fixture
async def admin_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/v1/auth/register",
            json={"name": "Admin", "email": "admin@example.com", "password": "correct-password-1"},
        )
        await ac.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "correct-password-1"},
        )

        # There is no public "become an admin" endpoint by design - promote
        # directly in the DB. get_current_user re-fetches the role from the
        # DB on every request (a Phase 2 decision), so the existing access
        # token cookie reflects this immediately without re-login.
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == "admin@example.com"))
            user = result.scalar_one()
            user.role = UserRole.ADMIN
            await session.commit()

        yield ac
