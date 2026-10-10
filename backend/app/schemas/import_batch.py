from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ImportStatus


class ImportBatchPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    uploaded_by: int | None
    exam_id: int | None
    status: ImportStatus
    error_log: str | None
    created_at: datetime
    updated_at: datetime


class ImportBatchSummary(ImportBatchPublic):
    """ImportBatchPublic plus counts the review screen needs, without
    pulling the (large) raw_extraction JSONB blob into every list response."""

    question_count: int
    pending_review_count: int
    published_count: int
    missing_correct_option_count: int
