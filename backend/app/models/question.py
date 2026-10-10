from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import QuestionStatus


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    exam_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exams.id", ondelete="RESTRICT"))
    subject_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("subjects.id", ondelete="RESTRICT"))
    topic_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("topics.id", ondelete="RESTRICT"))
    question_number: Mapped[int | None] = mapped_column(SmallInteger)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_image_url: Mapped[str | None] = mapped_column(String(500))
    # Shared comprehension-passage text (PDF import only). Consecutive
    # questions in an attempt that carry identical passage_text are rendered
    # as one shared passage block by the client - no separate passages table
    # is needed since passages are only ever consumed through the existing
    # ordered attempt_questions sequence.
    passage_text: Mapped[str | None] = mapped_column(Text)
    correct_option: Mapped[str | None] = mapped_column(CHAR(1))
    positive_marks: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("2.00"))
    negative_marks: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default=text("0.50"))
    solution_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[QuestionStatus] = mapped_column(
        SAEnum(QuestionStatus, name="question_status", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default=text("'draft'"),
    )
    import_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("import_batches.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exam: Mapped["Exam | None"] = relationship(back_populates="questions")
    subject: Mapped["Subject | None"] = relationship(back_populates="questions")
    topic: Mapped["Topic | None"] = relationship(back_populates="questions")
    import_batch: Mapped["ImportBatch | None"] = relationship(back_populates="questions")
    options: Mapped[list["QuestionOption"]] = relationship(back_populates="question")

    __table_args__ = (
        UniqueConstraint("exam_id", "question_number", name="uq_questions_exam_id_question_number"),
        CheckConstraint("correct_option IN ('A','B','C','D')", name="ck_questions_correct_option_values"),
        CheckConstraint("positive_marks >= 0", name="ck_questions_positive_marks_nonneg"),
        CheckConstraint("negative_marks >= 0", name="ck_questions_negative_marks_nonneg"),
        # topic_id is intentionally NOT required here (Phase 9 final fix):
        # topic classification doesn't happen at all for now, imported or
        # manually entered - only subject + a correct answer gate publish.
        CheckConstraint(
            "status <> 'published' OR (subject_id IS NOT NULL AND correct_option IS NOT NULL)",
            name="ck_questions_publish_readiness",
        ),
        Index("ix_questions_exam_id", "exam_id"),
        Index("ix_questions_topic_id", "topic_id"),
        Index("ix_questions_subject_id", "subject_id"),
        Index("ix_questions_status", "status"),
    )
