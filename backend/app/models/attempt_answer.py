from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    selected_option: Mapped[str | None] = mapped_column(CHAR(1))
    marked_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)

    attempt: Mapped["Attempt"] = relationship(back_populates="attempt_answers")
    question: Mapped["Question"] = relationship()

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answers_attempt_id_question_id"),
        CheckConstraint("selected_option IN ('A','B','C','D')", name="ck_attempt_answers_selected_option_values"),
        CheckConstraint(
            "time_spent_seconds IS NULL OR time_spent_seconds >= 0",
            name="ck_attempt_answers_time_spent_nonneg",
        ),
        Index("ix_attempt_answers_attempt_id", "attempt_id"),
    )
