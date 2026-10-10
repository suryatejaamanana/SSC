from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.enums import ImportStatus


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    exam_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("exams.id", ondelete="SET NULL"))
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus, name="import_status", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        server_default=text("'processing'"),
    )
    raw_extraction: Mapped[dict | None] = mapped_column(JSONB)
    error_log: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exam: Mapped["Exam | None"] = relationship(back_populates="import_batches")
    questions: Mapped[list["Question"]] = relationship(back_populates="import_batch")

    __table_args__ = (
        Index("ix_import_batches_status", "status"),
        Index("ix_import_batches_uploaded_by", "uploaded_by"),
    )
