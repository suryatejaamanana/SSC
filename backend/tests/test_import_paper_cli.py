import argparse
from pathlib import Path

import pytest

from app.core.config import Settings
from scripts import import_paper
from scripts.import_paper import TargetError, confirm_target, resolve_target

FIXTURE = Path(__file__).parent / "fixtures" / "ssc_cgl_2024_tier1_09_sep.pdf"
NEON_DIRECT = "postgresql://neon_user:hunter2-db-password@ep-cool-rain-123456.us-east-2.aws.neon.tech/neondb?sslmode=require"
NEON_POOLED = NEON_DIRECT.replace("ep-cool-rain-123456", "ep-cool-rain-123456-pooler")
LOCAL_DB = "postgresql://ssc_cgl:change_me@localhost:5432/ssc_cgl"
NEON_HOST = "ep-cool-rain-123456.us-east-2.aws.neon.tech"


def _settings(db: str, backend: str) -> Settings:
    extra = {}
    if backend == "b2":
        extra = dict(
            b2_endpoint_url="https://s3.us-west-004.backblazeb2.com",
            b2_bucket="govt-exam-media",
            b2_key_id="kid-0123456789",
            b2_application_key="sekret-application-key",
        )
    return Settings(_env_file=None, database_url=db, jwt_secret_key="x", media_backend=backend, **extra)


def _never_asked(prompt: str) -> str:
    raise AssertionError(f"must not prompt: {prompt}")


# --- target classification ---------------------------------------------------

def test_local_database_with_local_media_is_a_local_target():
    target = resolve_target(_settings(LOCAL_DB, "local"))
    assert not target.is_production and target.db_host == "localhost"


def test_neon_direct_with_b2_is_a_production_target():
    target = resolve_target(_settings(NEON_DIRECT, "b2"))
    assert target.is_production and target.db_host == NEON_HOST and target.bucket == "govt-exam-media"


def test_remote_database_with_local_media_is_rejected():
    with pytest.raises(TargetError, match="local-disk media"):
        resolve_target(_settings(NEON_DIRECT, "local"))


def test_local_database_with_b2_bucket_is_rejected():
    with pytest.raises(TargetError, match="local database with a B2 bucket"):
        resolve_target(_settings(LOCAL_DB, "b2"))


def test_pooled_neon_endpoint_is_rejected():
    with pytest.raises(TargetError, match="pooled"):
        resolve_target(_settings(NEON_POOLED, "b2"))


# --- confirmation rules ------------------------------------------------------

def test_local_target_allows_yes_flag_without_prompting():
    target = resolve_target(_settings(LOCAL_DB, "local"))
    assert confirm_target(target, assume_yes=True, interactive=False, ask=_never_asked) is True


@pytest.mark.parametrize("answer, expected", [("y", True), ("Y", True), ("n", False), ("", False)])
def test_local_target_prompts_otherwise(answer, expected):
    target = resolve_target(_settings(LOCAL_DB, "local"))
    assert confirm_target(target, assume_yes=False, interactive=True, ask=lambda _p: answer) is expected


def test_production_requires_typing_the_exact_database_host():
    target = resolve_target(_settings(NEON_DIRECT, "b2"))
    assert confirm_target(target, assume_yes=False, interactive=True, ask=lambda _p: NEON_HOST) is True
    for wrong in ("y", "yes", "", "ep-cool-rain-123456", NEON_HOST + "x"):
        assert confirm_target(target, assume_yes=False, interactive=True, ask=lambda _p, w=wrong: w) is False


def test_yes_flag_is_refused_not_ignored_for_production():
    target = resolve_target(_settings(NEON_DIRECT, "b2"))
    with pytest.raises(TargetError, match="--yes is not accepted"):
        confirm_target(target, assume_yes=True, interactive=True, ask=_never_asked)


def test_production_refuses_a_non_interactive_session():
    target = resolve_target(_settings(NEON_DIRECT, "b2"))
    with pytest.raises(TargetError, match="interactive terminal"):
        confirm_target(target, assume_yes=False, interactive=False, ask=_never_asked)


# --- output never contains credentials ---------------------------------------

def test_target_description_shows_host_and_storage_but_no_credentials():
    text = resolve_target(_settings(NEON_DIRECT, "b2")).describe()
    assert NEON_HOST in text and "govt-exam-media" in text and "PRODUCTION" in text
    for secret in ("hunter2-db-password", "neon_user", "sekret-application-key", "kid-0123456789", "sslmode"):
        assert secret not in text


# --- the CLI entry point stops before touching the database ------------------

def _args(**overrides) -> argparse.Namespace:
    base = dict(pdf=str(FIXTURE), year=2024, tier="Tier 1", admin_email="a@example.com", yes=False)
    base.update(overrides)
    return argparse.Namespace(**base)


@pytest.fixture
def no_db_access(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("the importer touched the database before the safety checks passed")

    monkeypatch.setattr(import_paper, "AsyncSessionLocal", boom)
    monkeypatch.setattr(import_paper.pdf_import_service, "run_import", boom)


@pytest.mark.parametrize(
    "db, backend, args",
    [
        (NEON_DIRECT, "local", {}),
        (LOCAL_DB, "b2", {}),
        (NEON_POOLED, "b2", {}),
        (NEON_DIRECT, "b2", {"yes": True}),  # --yes on production
        (NEON_DIRECT, "b2", {}),  # production, but pytest has no interactive stdin
    ],
)
async def test_run_aborts_before_any_database_access(monkeypatch, no_db_access, capsys, db, backend, args):
    monkeypatch.setattr(import_paper, "get_settings", lambda: _settings(db, backend))
    assert await import_paper._run(_args(**args)) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith("error:")
    for secret in ("hunter2-db-password", "sekret-application-key", "kid-0123456789"):
        assert secret not in captured.out + captured.err


async def test_run_declined_confirmation_imports_nothing(monkeypatch, no_db_access, capsys):
    monkeypatch.setattr(import_paper, "get_settings", lambda: _settings(LOCAL_DB, "local"))
    monkeypatch.setattr("builtins.input", lambda _p: "n")
    assert await import_paper._run(_args()) == 1
    assert "aborted" in capsys.readouterr().out
