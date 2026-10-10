import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_accepts_a_percent_encoded_database_password():
    """Regression: env.py passed the URL to ConfigParser, which treats '%' as
    interpolation syntax, so a percent-encoded password (p%40ss = "p@ss")
    crashed every `alembic` command - and start.sh runs it on each boot.
    Offline mode (--sql) builds the full migration script without ever
    connecting, so the unreachable port is never contacted."""
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql://neon_user:p%40ss%25word@localhost:1/db?sslmode=require",
    }
    env.pop("PGHOST", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-600:]
    assert "CREATE TABLE users" in result.stdout
    assert "p%40ss" not in result.stdout + result.stderr  # credentials are never echoed
