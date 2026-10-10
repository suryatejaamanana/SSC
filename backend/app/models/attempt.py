from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import AttemptStatus, AttemptType


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exams.id", ondelete="RESTRICT"))
    topic_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("topics.id", ondelete="RESTRICT"))
    # Set only for attempt_type='section_practice' - identifies which of the
    # exam's sections (subject) this practice session was scoped to.
    subject_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="RESTRICT"))
    attempt_type: Mapped[AttemptType] = mapped_column(
        SAEnum(AttemptType, name="attempt_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    status: Mapped[AttemptStatus] = mapped_column(
        SAEnum(AttemptStatus, name="attempt_status", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default=text("'in_progress'"),
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    correct_count: Mapped[int | None] = mapped_column(SmallInteger)
    wrong_count: Mapped[int | None] = mapped_column(SmallInteger)
    unanswered_count: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="attempts")
    exam: Mapped["Exam | None"] = relationship(back_populates="attempts")
    topic: Mapped["Topic | None"] = relationship(back_populates="attempts")
    subject: Mapped["Subject | None"] = relationship()
    attempt_questions: Mapped[list["AttemptQuestion"]] = relationship(back_populates="attempt")
    attempt_answers: Mapped[list["AttemptAnswer"]] = relationship(back_populates="attempt")

    __table_args__ = (
        CheckConstraint(
            "(attempt_type = 'full_paper' AND exam_id IS NOT NULL AND topic_id IS NULL AND subject_id IS NULL) OR "
            "(attempt_type = 'topic_practice' AND topic_id IS NOT NULL AND exam_id IS NULL AND subject_id IS NULL) OR "
            "(attempt_type = 'section_practice' AND exam_id IS NOT NULL AND topic_id IS NULL AND subject_id IS NOT NULL)",
            name="ck_attempts_type_exam_topic_consistency",
        ),
        CheckConstraint(
            "status = 'in_progress' OR (submitted_at IS NOT NULL AND score IS NOT NULL)",
            name="ck_attempts_terminal_status_requires_result",
        ),
        Index("ix_attempts_user_id", "user_id"),
        Index("ix_attempts_exam_id", "exam_id"),
        Index("ix_attempts_topic_id", "topic_id"),
        Index("ix_attempts_subject_id", "subject_id"),
        Index(
            "ix_attempts_in_progress_expires_at",
            "expires_at",
            postgresql_where=text("status = 'in_progress'"),
        ),
    )
