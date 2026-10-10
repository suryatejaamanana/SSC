from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.deps import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories import question_repository
from app.services import media_storage

router = APIRouter(prefix="/media", tags=["media"], dependencies=[Depends(get_current_user)])


@router.get("/{path:path}")
async def get_media(
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serves PDF-import-extracted question/option images. Never serves the
    original uploaded PDF (see media_storage.resolve_media_path) or anything
    outside the media root; this is intentionally not a bare static-file
    mount.

    A non-admin may only view an image that belongs to an already-published
    question - filenames here are predictable (sequential batch ids,
    "s{shift}_q{n}_..."), so without this check a student could enumerate
    the figures of a question still in draft/pending_review/archived before
    it's actually published, the same content-leak the rest of the student
    API is careful to avoid (see e.g. exam_service.get_published_exam).
    Admins may preview any image, same as they can see any question.
    """
    resolved = media_storage.resolve_media_path(path)

    if current_user.role != UserRole.ADMIN:
        url = f"/api/v1/media/{path}"
        if not await question_repository.image_url_belongs_to_published_question(db, url):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    return FileResponse(resolved)
