from datetime import datetime

from sqlalchemy import CHAR, BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    question: Mapped["Question"] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("question_id", "label", name="uq_question_options_question_id_label"),
        CheckConstraint("label IN ('A','B','C','D')", name="ck_question_options_label_values"),
        CheckConstraint("text IS NOT NULL OR image_url IS NOT NULL", name="ck_question_options_content_present"),
    )
