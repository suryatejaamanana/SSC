import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.db_guard import UnsafeTestDatabase, assert_local_test_database

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@localhost:5432/db",
        "postgresql+asyncpg://u:p@LOCALHOST/db",
        "postgresql+asyncpg://u:p@127.0.0.1:55432/db",
        "postgresql+asyncpg://u:p@[::1]:5432/db",
        "postgresql+asyncpg://u:p@db:5432/db",
        "postgresql+asyncpg://u:p@localhost/db?ssl=disable",
        "postgresql+asyncpg://u@/db?host=/var/run/postgresql",
    ],
)
def test_local_databases_are_allowed(url, monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    assert_local_test_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@ep-cool-rain-123456.us-east-2.aws.neon.tech/neondb?ssl=require",
        "postgresql+asyncpg://u:p@ep-cool-rain-123456-pooler.us-east-2.aws.neon.tech/neondb",
        "postgresql+asyncpg://u:p@10.0.0.5:5432/db",
        "postgresql+asyncpg://u:p@db.internal.example.com/db",
        "postgresql+asyncpg://u:p@localhost.evil.example/db",  # looks local, is not
        "postgresql+asyncpg://localhost:p@evil.example/db",  # 'localhost' is only the username
        "postgresql+asyncpg://u:p@localhost/db?host=evil.example",  # ?host= wins in asyncpg
        "postgresql+asyncpg://u:p@localhost,evil.example/db",  # multi-host list
        "postgresql+asyncpg://u:p@evil.example/db?host=localhost",
        "postgresql+asyncpg://u:p@[2001:db8::1]:5432/db",
    ],
)
def test_remote_databases_are_refused(url, monkeypatch):
    monkeypatch.delenv("PGHOST", raising=False)
    with pytest.raises(UnsafeTestDatabase, match="Refusing to run the tests"):
        assert_local_test_database(url)


def test_url_without_a_host_is_judged_by_pghost(monkeypatch):
    url = "postgresql+asyncpg://u:p@/db"
    monkeypatch.setenv("PGHOST", "ep-x.us-east-2.aws.neon.tech")
    with pytest.raises(UnsafeTestDatabase):
        assert_local_test_database(url)
    monkeypatch.setenv("PGHOST", "localhost")
    assert_local_test_database(url)
    monkeypatch.delenv("PGHOST")
    assert_local_test_database(url)


def test_refusal_message_never_contains_the_password():
    with pytest.raises(UnsafeTestDatabase) as exc:
        assert_local_test_database("postgresql+asyncpg://neon_user:SuperSecretPw@remote.invalid/db")
    assert "SuperSecretPw" not in str(exc.value) and "neon_user" not in str(exc.value)
    assert "remote.invalid" in str(exc.value)


def test_pytest_aborts_before_running_anything_against_a_remote_database():
    """Runs a nested pytest whose DATABASE_URL is a remote host (the reserved
    .invalid TLD never resolves, and the guard stops the run before any
    connection anyway) and checks that nothing executes."""
    env = {**os.environ, "DATABASE_URL": "postgresql://u:NestedSecretPw@remote.invalid:5432/db"}
    env.pop("PGHOST", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_db_guard.py", "-p", "no:cacheprovider", "-q"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Refusing to run the tests" in output and "remote.invalid" in output
    assert "NestedSecretPw" not in output
    assert "passed" not in output  # no test ran, not even the guard's own tests
