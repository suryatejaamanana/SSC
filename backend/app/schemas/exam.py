from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Mirrors the DB CHECK constraint ck_exams_tier_values exactly - validating it
# here too gives a clearer 422 before the request even reaches the database.
Tier = Literal["Tier 1", "Tier 2"]


class ExamCreate(BaseModel):
    year: int = Field(ge=2010, le=2100)
    tier: Tier
    shift: int = Field(default=1, ge=1)
    exam_date: date | None = None
    duration_minutes: int = Field(gt=0)
    total_questions: int = Field(gt=0)
    total_marks: Decimal = Field(gt=0)
    source_pdf_name: str | None = None


class ExamUpdate(BaseModel):
    # is_published is deliberately absent - only POST /exams/{id}/publish,
    # which runs the content-validation rules, may set it.
    year: int | None = Field(default=None, ge=2010, le=2100)
    tier: Tier | None = None
    shift: int | None = Field(default=None, ge=1)
    exam_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    total_questions: int | None = Field(default=None, gt=0)
    total_marks: Decimal | None = Field(default=None, gt=0)
    source_pdf_name: str | None = None


class ExamPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    tier: str
    shift: int
    exam_date: date | None
    duration_minutes: int
    total_questions: int
    total_marks: Decimal
    is_published: bool
    source_pdf_name: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
