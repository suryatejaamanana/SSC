from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.deps import get_db
from app.models.user import User
from app.repositories import import_batch_repository
from app.schemas.import_batch import ImportBatchPublic, ImportBatchSummary
from app.schemas.question import QuestionPublic
from app.services import media_storage, pdf_import_service, question_service

router = APIRouter(
    prefix="/admin/imports",
    tags=["admin:imports"],
    dependencies=[Depends(require_role("admin"))],
)

# Mirrors schemas.exam.Tier - validated here too for a clean 422 on upload.
Tier = Literal["Tier 1", "Tier 2"]


async def _to_summary(db: AsyncSession, batch) -> ImportBatchSummary:
    total, pending, published, missing_correct = await import_batch_repository.question_counts(
        db, batch.id
    )
    return ImportBatchSummary(
        id=batch.id,
        filename=batch.filename,
        uploaded_by=batch.uploaded_by,
        exam_id=batch.exam_id,
        status=batch.status,
        error_log=batch.error_log,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        question_count=total,
        pending_review_count=pending,
        published_count=published,
        missing_correct_option_count=missing_correct,
    )


async def _get_batch_or_404(db: AsyncSession, batch_id: int):
    batch = await import_batch_repository.get_by_id(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import batch not found")
    return batch


@router.post("", response_model=ImportBatchPublic, status_code=status.HTTP_201_CREATED)
async def upload_import(
    year: int = Form(..., ge=2010, le=2100),
    tier: Tier = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pdf_bytes = await pdf_import_service.validate_upload(file)
    batch = await pdf_import_service.run_import(
        db,
        filename=file.filename or "upload.pdf",
        pdf_bytes=pdf_bytes,
        year=year,
        tier=tier,
        uploaded_by=current_user.id,
    )
    return batch


@router.get("", response_model=list[ImportBatchSummary])
async def list_imports(db: AsyncSession = Depends(get_db)):
    batches = await import_batch_repository.list_all(db)
    return [await _to_summary(db, b) for b in batches]


@router.get("/{batch_id}", response_model=ImportBatchSummary)
async def get_import(batch_id: int, db: AsyncSession = Depends(get_db)):
    batch = await _get_batch_or_404(db, batch_id)
    return await _to_summary(db, batch)


@router.get("/{batch_id}/questions", response_model=list[QuestionPublic])
async def list_import_questions(batch_id: int, db: AsyncSession = Depends(get_db)):
    await _get_batch_or_404(db, batch_id)
    return await question_service.list_questions(db, import_batch_id=batch_id)


@router.get("/{batch_id}/source")
async def download_source_pdf(batch_id: int, db: AsyncSession = Depends(get_db)):
    """Admin-only retrieval of the original uploaded PDF. Deliberately a
    separate, explicitly-admin-gated route rather than anything reachable
    through the generic /api/v1/media route, which only ever serves the
    extracted question/option images."""
    batch = await _get_batch_or_404(db, batch_id)

    path = media_storage.source_pdf_path(batch_id)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source PDF not found")

    return FileResponse(path, media_type="application/pdf", filename=batch.filename)
