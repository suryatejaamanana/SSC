"""Import one SSC CGL paper PDF from the command line.

Runs the exact same pipeline as POST /api/v1/admin/imports, but outside the
web service - use it to load papers into the production Neon database and B2
bucket from your own machine (the Render free instance is too small to parse
PDFs). Configure the target through environment variables (DATABASE_URL,
MEDIA_BACKEND=b2, B2_*); credentials are never printed.

    python -m scripts.import_paper path/to/paper.pdf --year 2024 --tier "Tier 1" \
        --admin-email you@example.com

Safety rules (enforced before anything is read from or written to the target):
  * A target is "local" when the database host is this machine, and
    "production" otherwise.
  * Mixed targets are rejected with no override: a remote database with
    local-disk media (the deployed app could never serve the images), a local
    database with a B2 bucket (a dev run would write into the real bucket),
    and a Neon "-pooler" host (use the direct connection string).
  * A production import needs the database host typed back exactly at an
    interactive prompt. --yes is accepted only for local targets and is
    refused (not ignored) for production.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.session import AsyncSessionLocal, engine
from app.models.enums import UserRole
from app.models.user import User
from app.services import pdf_import_service

_LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal", "db"}


class TargetError(Exception):
    """The configured import target is unsafe or inconsistent."""


@dataclass(frozen=True)
class Target:
    db_host: str
    is_production: bool
    media_backend: str
    bucket: str
    media_root: str

    def describe(self) -> str:
        kind = "PRODUCTION" if self.is_production else "local"
        media = (
            f"b2 bucket '{self.bucket}'" if self.media_backend == "b2" else f"local dir '{self.media_root}'"
        )
        return (
            f"  target:   {kind}\n"
            f"  database: host '{self.db_host or 'local socket'}'\n"
            f"  storage:  {media}"
        )


def resolve_target(settings: Settings) -> Target:
    """Classifies the configured target and rejects mixed/unsafe setups."""
    db_host = (urlsplit(settings.database_url).hostname or "").lower()
    is_production = db_host not in _LOCAL_HOSTS
    target = Target(
        db_host=db_host,
        is_production=is_production,
        media_backend=settings.media_backend,
        bucket=settings.b2_bucket,
        media_root=settings.media_root,
    )

    if is_production and settings.media_backend != "b2":
        raise TargetError(
            f"remote database '{db_host}' with local-disk media: the images would only exist on this "
            "machine and the deployed app could never serve them. Set MEDIA_BACKEND=b2 with the B2_* "
            "variables, or point DATABASE_URL at a local database."
        )
    if not is_production and settings.media_backend == "b2":
        raise TargetError(
            "local database with a B2 bucket: a local/dev run would write into the real bucket. "
            "Point DATABASE_URL at the production database, or use MEDIA_BACKEND=local."
        )
    if is_production and "-pooler" in db_host:
        raise TargetError(
            f"'{db_host}' is a pooled (PgBouncer) endpoint; use the direct connection string "
            "(host without '-pooler')."
        )
    return target


def confirm_target(
    target: Target,
    *,
    assume_yes: bool,
    interactive: bool,
    ask: Callable[[str], str] | None = None,
) -> bool:
    """Returns True to proceed. Raises TargetError when --yes is used on a
    production target or a production import is attempted without a terminal."""
    ask = ask or input
    if not target.is_production:
        if assume_yes:
            return True
        return ask("Proceed with this LOCAL import? [y/N] ").strip().lower() == "y"

    if assume_yes:
        raise TargetError("--yes is not accepted for production imports; confirm interactively.")
    if not interactive:
        raise TargetError("production imports need an interactive terminal for confirmation.")
    typed = ask(f"This writes to PRODUCTION. Type the database host '{target.db_host}' to continue: ")
    return typed.strip() == target.db_host


async def _run(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"error: {pdf_path} not found", file=sys.stderr)
        return 2
    pdf_bytes = pdf_path.read_bytes()
    settings = get_settings()
    if not pdf_bytes.startswith(b"%PDF") or len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        print("error: not a PDF, or larger than MAX_UPLOAD_MB", file=sys.stderr)
        return 2

    try:
        target = resolve_target(settings)
        print(f"Import target:\n{target.describe()}")
        proceed = confirm_target(target, assume_yes=args.yes, interactive=sys.stdin.isatty())
    except TargetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not proceed:
        print("aborted")
        return 1

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == args.admin_email))).scalar_one_or_none()
        if user is None or user.role != UserRole.ADMIN:
            print("error: --admin-email must be an existing admin account", file=sys.stderr)
            return 2
        batch = await pdf_import_service.run_import(
            db,
            filename=pdf_path.name,
            pdf_bytes=pdf_bytes,
            year=args.year,
            tier=args.tier,
            uploaded_by=user.id,
        )
        print(f"batch {batch.id}: {batch.status.value}")
        if batch.error_log:
            print(f"error_log: {batch.error_log}")
        return 0 if batch.status.value != "failed" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--tier", choices=["Tier 1", "Tier 2"], required=True)
    parser.add_argument("--admin-email", required=True, help="existing admin account recorded as uploader")
    parser.add_argument("--yes", action="store_true", help="skip the prompt (local targets only)")
    args = parser.parse_args()

    async def runner() -> int:
        try:
            return await _run(args)
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(runner()))


if __name__ == "__main__":
    main()
