from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    attempt: Mapped["Attempt"] = relationship(back_populates="attempt_questions")
    question: Mapped["Question"] = relationship()

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_questions_attempt_id_question_id"),
        UniqueConstraint("attempt_id", "order_index", name="uq_attempt_questions_attempt_id_order_index"),
        CheckConstraint("order_index >= 0", name="ck_attempt_questions_order_index_nonneg"),
        Index("ix_attempt_questions_question_id", "question_id"),
    )
