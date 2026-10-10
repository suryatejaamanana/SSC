from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    shift: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    exam_date: Mapped[date | None] = mapped_column(Date)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_questions: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source_pdf_name: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    questions: Mapped[list["Question"]] = relationship(back_populates="exam")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="exam")
    import_batches: Mapped[list["ImportBatch"]] = relationship(back_populates="exam")

    __table_args__ = (
        UniqueConstraint("year", "tier", "shift", name="uq_exams_year_tier_shift"),
        CheckConstraint("year BETWEEN 2010 AND 2100", name="ck_exams_year_range"),
        CheckConstraint("tier IN ('Tier 1', 'Tier 2')", name="ck_exams_tier_values"),
        CheckConstraint("shift >= 1", name="ck_exams_shift_positive"),
        CheckConstraint("duration_minutes > 0", name="ck_exams_duration_positive"),
        CheckConstraint("total_questions > 0", name="ck_exams_total_questions_positive"),
        CheckConstraint("total_marks > 0", name="ck_exams_total_marks_positive"),
        Index("ix_exams_is_published", "is_published"),
    )
