from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import QuestionStatus

# Pydantic's Literal type already rejects any label outside A-D at the
# request-validation layer (a 422 before the service even runs) - so only
# duplicate-label checking needs an explicit validator below.
OptionLabel = Literal["A", "B", "C", "D"]


def _assert_unique_labels(options: list["QuestionOptionCreate"]) -> None:
    labels = [opt.label for opt in options]
    if len(labels) != len(set(labels)):
        raise ValueError("Duplicate option labels are not allowed.")


class QuestionOptionCreate(BaseModel):
    label: OptionLabel
    text: str | None = None
    image_url: str | None = None


class QuestionOptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    text: str | None
    image_url: str | None


class QuestionCreate(BaseModel):
    exam_id: int | None = None
    subject_id: int | None = None
    topic_id: int | None = None
    question_number: int | None = Field(default=None, gt=0)
    question_text: str = Field(min_length=1)
    question_image_url: str | None = None
    correct_option: OptionLabel | None = None
    positive_marks: Decimal = Field(default=Decimal("2.00"), ge=0)
    negative_marks: Decimal = Field(default=Decimal("0.50"), ge=0)
    solution_text: str | None = None
    passage_text: str | None = None
    options: list[QuestionOptionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique_option_labels(self) -> "QuestionCreate":
        _assert_unique_labels(self.options)
        return self


class QuestionUpdate(BaseModel):
    # status excludes "published" at the type level - that transition is only
    # reachable through POST /questions/{id}/publish, which runs the full
    # publish-readiness validation (text, subject, topic, correct_option,
    # exactly 4 valid options, marks).
    exam_id: int | None = None
    subject_id: int | None = None
    topic_id: int | None = None
    question_number: int | None = Field(default=None, gt=0)
    question_text: str | None = Field(default=None, min_length=1)
    question_image_url: str | None = None
    correct_option: OptionLabel | None = None
    positive_marks: Decimal | None = Field(default=None, ge=0)
    negative_marks: Decimal | None = Field(default=None, ge=0)
    solution_text: str | None = None
    passage_text: str | None = None
    status: Literal["draft", "pending_review", "archived"] | None = None
    options: list[QuestionOptionCreate] | None = None

    @model_validator(mode="after")
    def _check_unique_option_labels(self) -> "QuestionUpdate":
        if self.options is not None:
            _assert_unique_labels(self.options)
        return self


class QuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int | None
    subject_id: int | None
    topic_id: int | None
    question_number: int | None
    question_text: str
    question_image_url: str | None
    correct_option: str | None
    positive_marks: Decimal
    negative_marks: Decimal
    solution_text: str | None
    passage_text: str | None
    status: QuestionStatus
    import_batch_id: int | None
    created_at: datetime
    updated_at: datetime
    options: list[QuestionOptionPublic] = Field(default_factory=list)
