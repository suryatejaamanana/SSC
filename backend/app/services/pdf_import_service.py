"""Orchestrates a PDF import: validates the upload, stores the original
file, runs app.services.pdf_extractor over it, and persists the extracted
questions as Question rows.

Per the Phase 9 final-check requirement, there is no individual admin
approval step: a question that comes out of extraction with everything the
existing publish-readiness rule requires (text, subject, correct_option,
exactly 4 valid options) is published immediately, and so is its exam once
every one of its questions is - students can practice right after upload.

correct_option is set ONLY from pdf_extractor's verified green-marking
detection (ExtractedQuestion.correct_option) - never from the candidate's
own "Chosen Option" (ExtractedQuestion.chosen_option_number), which is
preserved solely as metadata in import_batches.raw_extraction. When the
extractor could not determine a question's correct answer with confidence,
correct_option stays NULL, the question is flagged in raw_extraction, and
it is left pending_review rather than guessed or force-published - the
existing publish-readiness check naturally blocks it (and, transitively,
its exam) until an admin fills it in by hand. This is the only path by
which a question can still need manual attention; it is not a review step
in the normal flow.

No topic classification happens at all (Phase 9 final fix): topic_id is
always left NULL on import, and the publish-readiness rule no longer
requires it (for any question, imported or manually entered - see
question_service.validate_question_for_publish and the
ck_questions_publish_readiness constraint).
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from datetime import date as date_type
from decimal import Decimal

import pdfplumber
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import ImportStatus, QuestionStatus
from app.models.exam import Exam
from app.models.import_batch import ImportBatch
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.repositories import exam_repository, question_repository, subject_repository
from app.services import exam_service, media_storage, question_service
from app.services.pdf_extractor import ExtractedQuestion, ExtractedShift, crop_region, extract

settings = get_settings()
logger = logging.getLogger(__name__)

DEFAULT_POSITIVE_MARKS = Decimal("2.00")
DEFAULT_NEGATIVE_MARKS = Decimal("0.50")

# A small number of stems (verified: whole-table/graph QA questions) extract
# with zero surrounding text - the entire stem is the captured image. The
# existing "question text is required" publish rule is a general, Phase 1
# invariant left untouched here; this placeholder satisfies it honestly
# (the real content is the attached image, which the student UI always
# renders) instead of leaving such a question stuck needing manual text
# entry, which would defeat the no-manual-approval requirement for no
# reason - nothing about the image is reinterpreted or guessed.
QUESTION_TEXT_IMAGE_PLACEHOLDER = "See the attached image for this question."

_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}):(\d{2})\s*(AM|PM)\s*-\s*(\d{1,2}):(\d{2})\s*(AM|PM)", re.IGNORECASE
)


def _parse_duration_minutes(exam_time: str | None) -> int:
    """Parses e.g. '9:00 AM - 10:00 AM' into 60. Falls back to a safe
    default (60, SSC CGL Tier 1's standard duration) if the time range in
    the PDF can't be parsed, rather than failing the whole import."""
    if not exam_time:
        return 60
    m = _TIME_RANGE_RE.search(exam_time)
    if not m:
        return 60

    def to_minutes(h, mnt, ampm):
        h = int(h)
        mnt = int(mnt)
        ampm = ampm.upper()
        if ampm == "AM":
            h = 0 if h == 12 else h
        else:
            h = 12 if h == 12 else h + 12
        return h * 60 + mnt

    start = to_minutes(m.group(1), m.group(2), m.group(3))
    end = to_minutes(m.group(4), m.group(5), m.group(6))
    diff = end - start
    if diff <= 0:
        diff += 24 * 60
    return diff


def _parse_exam_date(exam_date: str | None) -> date_type | None:
    if not exam_date:
        return None
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", exam_date)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date_type(year, month, day)
    except ValueError:
        return None


_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024  # 1MB


async def validate_upload(file: UploadFile) -> bytes:
    if file.content_type not in ("application/pdf", "application/octet-stream") and not (
        file.filename or ""
    ).lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only PDF files are accepted"
        )

    # Read in bounded chunks and bail out as soon as the limit is exceeded,
    # rather than buffering an arbitrarily large upload in full before ever
    # checking its size - content_type/filename are client-supplied and
    # prove nothing on their own, so an oversized or malicious upload must
    # still be rejected as cheaply as possible.
    max_bytes = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File exceeds the {settings.max_upload_mb}MB upload limit",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="File is not a valid PDF"
        )
    return data


async def _get_or_create_exam(
    db: AsyncSession, *, year: int, tier: str, shift: ExtractedShift, source_filename: str, created_by: int
) -> Exam:
    existing = await exam_repository.get_by_year_tier_shift(db, year, tier, shift.shift_index)
    if existing is not None:
        return existing

    duration_minutes = _parse_duration_minutes(shift.exam_time)
    total_questions = len(shift.questions) or 100
    exam = Exam(
        year=year,
        tier=tier,
        shift=shift.shift_index,
        exam_date=_parse_exam_date(shift.exam_date),
        duration_minutes=duration_minutes,
        total_questions=total_questions,
        total_marks=Decimal(total_questions) * DEFAULT_POSITIVE_MARKS,
        source_pdf_name=source_filename,
        created_by=created_by,
    )
    db.add(exam)
    await db.flush()
    return exam


async def _persist_question(
    db: AsyncSession,
    *,
    exam: Exam,
    subject_id: int | None,
    batch_id: int,
    extracted: ExtractedQuestion,
    question_image_url: str | None,
    option_image_urls: dict[str, str],
) -> Question:
    # Every option's final text/image_url is already known before the row is
    # ever inserted (images are cropped by the caller first) - inserting
    # with text=None, image_url=None and filling image_url in afterward
    # would violate ck_question_options_content_present the moment the
    # first INSERT flushes, since that constraint allows no gap between
    # "created" and "has content".
    question_text = extracted.question_text.strip() or (
        QUESTION_TEXT_IMAGE_PLACEHOLDER if question_image_url else extracted.question_text
    )
    question = Question(
        exam_id=exam.id,
        subject_id=subject_id,
        topic_id=None,  # no topic classification - see module docstring
        question_number=extracted.global_number,
        question_text=question_text,
        question_image_url=question_image_url,
        passage_text=extracted.passage_text,
        # From the verified green-marking detection ONLY - see module
        # docstring. NULL here means the extractor genuinely could not
        # determine it (flagged in raw_extraction), never a guess.
        correct_option=extracted.correct_option,
        positive_marks=DEFAULT_POSITIVE_MARKS,
        negative_marks=DEFAULT_NEGATIVE_MARKS,
        status=QuestionStatus.PENDING_REVIEW,
        import_batch_id=batch_id,
    )
    db.add(question)
    await db.flush()

    for option in extracted.options:
        db.add(
            QuestionOption(
                question_id=question.id,
                label=option.label,
                text=option.text,
                image_url=option_image_urls.get(option.label),
            )
        )
    await db.flush()
    return question


async def _try_publish_question(db: AsyncSession, question_id: int) -> bool:
    """Re-fetches the question (eager-loading its options, required for
    validate_question_for_publish and unsafe to read lazily under the async
    ORM right after the inserts above) and publishes it if - and only if -
    it already passes the exact same publish-readiness rule the admin-CRUD
    publish endpoint enforces. No rule is relaxed or duplicated; a question
    that wouldn't pass a manual admin publish doesn't get auto-published
    either, it just stays pending_review until someone fixes it by hand."""
    question = await question_repository.get_by_id(db, question_id)
    if question is None:
        return False
    errors = question_service.validate_question_for_publish(question)
    if errors:
        return False
    question.status = QuestionStatus.PUBLISHED
    await db.flush()
    return True


async def _try_publish_exam(db: AsyncSession, exam_id: int) -> bool:
    try:
        await exam_service.publish_exam(db, exam_id)
        return True
    except HTTPException as exc:
        if exc.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY:
            raise
        # Not every question in this exam auto-published (almost always
        # because one had no confidently-detected correct_option) - the exam
        # stays unpublished until that question is fixed, same as a manual
        # exam publish would behave.
        return False


def _crop_and_save(
    pdf: pdfplumber.PDF, *, batch_id: int, filename: str, page_number: int, bbox: tuple
) -> str:
    """Crops, saves, and returns the root-relative URL to store on
    question_image_url / option.image_url - resolvable by the frontend
    against the backend's own origin and servable only through the
    authenticated GET /api/v1/media/{path} route (see app.routers.v1.media
    and app.services.media_storage.validate_image_key)."""
    image = crop_region(pdf, page_number, bbox)
    relative_path = media_storage.save_image(batch_id, filename, image)
    return f"/api/v1/media/{relative_path}"


async def run_import(
    db: AsyncSession,
    *,
    filename: str,
    pdf_bytes: bytes,
    year: int,
    tier: str,
    uploaded_by: int,
) -> ImportBatch:
    # Committed immediately, in its own transaction, so the batch row still
    # exists (and can be marked 'failed' with a reason) even if everything
    # below raises - extraction/persistence runs in a separate transaction
    # from here on.
    batch = ImportBatch(filename=filename, uploaded_by=uploaded_by, status=ImportStatus.PROCESSING)
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    try:
        media_storage.save_source_pdf(batch.id, pdf_bytes)
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result = extract(pdf)

            if result.total_questions == 0:
                raise ValueError(
                    "No questions could be extracted from this PDF - it may not match the "
                    "expected SSC CGL response-sheet layout."
                )

            raw_questions_meta = []
            unresolved_correct_option = []
            published_question_count = 0
            published_exam_ids: list[int] = []

            for shift in result.shifts:
                exam = await _get_or_create_exam(
                    db,
                    year=year,
                    tier=tier,
                    shift=shift,
                    source_filename=filename,
                    created_by=uploaded_by,
                )

                for extracted in shift.questions:
                    subject_id = None
                    if extracted.subject_name:
                        subject = await subject_repository.get_or_create_by_name(
                            db, extracted.subject_name
                        )
                        subject_id = subject.id

                    # (shift_index, global_number) is unique within a batch,
                    # so these filenames can be computed before the question
                    # row (and its id) exists.
                    file_prefix = f"s{extracted.shift_index}_q{extracted.global_number}"

                    question_image_url = None
                    if extracted.question_image_bbox:
                        question_image_url = _crop_and_save(
                            pdf,
                            batch_id=batch.id,
                            filename=f"{file_prefix}_stem.png",
                            page_number=extracted.page_number,
                            bbox=extracted.question_image_bbox,
                        )

                    option_image_urls: dict[str, str] = {}
                    for extracted_option in extracted.options:
                        if extracted_option.image_bbox:
                            option_image_urls[extracted_option.label] = _crop_and_save(
                                pdf,
                                batch_id=batch.id,
                                filename=f"{file_prefix}_opt{extracted_option.label}.png",
                                page_number=extracted.page_number,
                                bbox=extracted_option.image_bbox,
                            )

                    question = await _persist_question(
                        db,
                        exam=exam,
                        subject_id=subject_id,
                        batch_id=batch.id,
                        extracted=extracted,
                        question_image_url=question_image_url,
                        option_image_urls=option_image_urls,
                    )

                    published = await _try_publish_question(db, question.id)
                    if published:
                        published_question_count += 1

                    raw_questions_meta.append(
                        {
                            "question_db_id": question.id,
                            "shift_index": extracted.shift_index,
                            "section_name": extracted.section_name,
                            "local_number": extracted.local_number,
                            "global_number": extracted.global_number,
                            "pdf_question_id": extracted.question_id,
                            "option_ids": {
                                o.label: o.option_id for o in extracted.options
                            },
                            "chosen_option_number": extracted.chosen_option_number,
                            "correct_option_detected": extracted.correct_option,
                            "published": published,
                            "response_status": extracted.status,
                            "warnings": extracted.warnings,
                        }
                    )

                    if extracted.correct_option is None:
                        unresolved_correct_option.append(
                            {
                                "question_db_id": question.id,
                                "shift_index": extracted.shift_index,
                                "section_name": extracted.section_name,
                                "local_number": extracted.local_number,
                                "reason": [
                                    w
                                    for w in extracted.warnings
                                    if w.startswith("correct-answer detection")
                                ],
                            }
                        )

                # All of this shift's questions are in - auto-publish its
                # exam too, so students see it immediately. Only succeeds if
                # every one of the exam's questions published above (same
                # rule a manual exam publish enforces); otherwise the exam
                # stays unpublished until the straggler question is fixed.
                if await _try_publish_exam(db, exam.id):
                    published_exam_ids.append(exam.id)

            batch.raw_extraction = {
                "questions": raw_questions_meta,
                "parser_warnings": result.warnings,
                "unresolved_correct_option": unresolved_correct_option,
                "published_question_count": published_question_count,
                "published_exam_ids": published_exam_ids,
            }
            # PUBLISHED only when every single extracted question actually
            # published (not just correct_option resolution - any other
            # publish-readiness failure counts too); PENDING_REVIEW still
            # means "something needs a human", same meaning it already had
            # before auto-publish existed.
            batch.status = (
                ImportStatus.PUBLISHED
                if published_question_count == len(raw_questions_meta)
                else ImportStatus.PENDING_REVIEW
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure here
        # must land the batch in `failed` with a readable reason, never leave
        # it stuck in `processing` or half-written, and never surface as a
        # bare 500 - a malformed/unexpected PDF is an expected outcome the
        # admin UI shows in the batch list, not a server error. Rolling back
        # discards every exam/subject/question this attempt created; `batch`
        # itself was already committed above, so it survives the rollback
        # and can still be updated below.
        await db.rollback()
        batch.status = ImportStatus.FAILED
        batch.error_log = str(exc)
        await db.commit()
        await _discard_extracted_images(batch.id)

    await db.refresh(batch)
    return batch


async def _discard_extracted_images(batch_id: int) -> None:
    """Best-effort removal of the cropped images a failed import already
    stored: the DB side was rolled back, so no question references them. The
    batch's source.pdf is deliberately kept - the failed batch row points to
    it and admins can still download it to see why the import failed. Runs
    only after the failed batch row is committed, and never raises: a cleanup
    problem must not mask the import's original error, so it is only logged
    (exception type only - no messages that could carry endpoint details).
    Anything left behind can be deleted by hand under imports/<batch_id>/images/."""
    try:
        await asyncio.to_thread(media_storage.delete_batch_images, batch_id)
    except Exception as cleanup_exc:  # noqa: BLE001 - see docstring
        logger.warning(
            "Could not clean up stored files for failed import batch %s (%s); "
            "delete imports/%s/images/ manually",
            batch_id,
            type(cleanup_exc).__name__,
            batch_id,
        )
