from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttemptStatus, AttemptType

OptionLabel = Literal["A", "B", "C", "D"]


class AttemptCreate(BaseModel):
    exam_id: int


class TopicPracticeAttemptCreate(BaseModel):
    topic_id: int
    question_count: int = Field(gt=0, le=100)


class SectionPracticeAttemptCreate(BaseModel):
    exam_id: int
    subject_id: int


class AttemptPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int | None
    topic_id: int | None
    subject_id: int | None
    attempt_type: AttemptType
    status: AttemptStatus
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    score: Decimal | None
    correct_count: int | None
    wrong_count: int | None
    unanswered_count: int | None
    created_at: datetime


class AnswerSubmit(BaseModel):
    question_id: int
    selected_option: OptionLabel | None = None
    marked_for_review: bool = False
    time_spent_seconds: int | None = Field(default=None, ge=0)


class AnswerPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: int
    selected_option: str | None
    marked_for_review: bool
    answered_at: datetime | None


class OptionForAttempt(BaseModel):
    label: str
    text: str | None
    image_url: str | None


class QuestionForAttempt(BaseModel):
    """Student-facing view of a question during an active attempt.

    Deliberately has no correct_option / solution_text / is_correct fields -
    those must never be exposed before submission.
    """

    question_id: int
    order_index: int
    question_number: int | None
    question_text: str
    question_image_url: str | None
    passage_text: str | None
    positive_marks: Decimal
    negative_marks: Decimal
    options: list[OptionForAttempt]
    selected_option: str | None
    marked_for_review: bool


class AttemptResult(BaseModel):
    attempt_id: int
    exam_id: int | None
    status: str
    total_questions: int
    attempted_count: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    score: Decimal
    accuracy: float
    time_taken_seconds: int
    started_at: datetime
    submitted_at: datetime


class ReviewItem(BaseModel):
    """Post-submission view - correct_option/solution_text are only ever
    constructed here, never in QuestionForAttempt."""

    question_id: int
    order_index: int
    question_number: int | None
    question_text: str
    question_image_url: str | None
    passage_text: str | None
    options: list[OptionForAttempt]
    selected_option: str | None
    correct_option: str | None
    is_correct: bool | None
    solution_text: str | None


class AttemptHistoryItem(BaseModel):
    """One row of history - frozen attempt-level aggregates only. No
    per-question data, so an answer key can never leak through here."""

    attempt_id: int
    attempt_type: AttemptType
    status: AttemptStatus
    exam_id: int | None
    exam_year: int | None
    exam_tier: str | None
    exam_shift: int | None
    topic_id: int | None
    topic_name: str | None
    subject_name: str | None
    started_at: datetime
    submitted_at: datetime | None
    score: Decimal | None
    correct_count: int | None
    wrong_count: int | None
    unanswered_count: int | None


class AttemptHistoryPage(BaseModel):
    items: list[AttemptHistoryItem]
    total: int
    limit: int
    offset: int


class AttemptHistorySummary(BaseModel):
    total_attempts: int
    total_questions: int
    total_correct: int
    total_wrong: int
    total_unanswered: int
    average_score: Decimal
    accuracy: float
    total_time_seconds: int


class SectionPerformance(BaseModel):
    """One of the 4 sections' aggregate performance across every one of the
    user's completed attempts (any attempt type) that included a question
    from that subject."""

    subject_id: int
    subject_name: str
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    accuracy: float
