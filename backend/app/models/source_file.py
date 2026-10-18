"""SourceFile model — one row per uploaded lecture file (PDF / PPTX ...)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import SourceFileStatus


class SourceFile(Base, TimestampMixin):
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # SHA-256 of the file bytes — used to de-duplicate re-uploads.
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=SourceFileStatus.UPLOADED.value,
        index=True,
    )

    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Staging area for the LLM output. `POST /files/{id}/generate` writes the
    # full structured draft here; `POST /files/{id}/publish` materialises it
    # into Topic/Lesson/Question/Flashcard rows. Keeping the draft on the row
    # means an interrupted publish can simply be retried.
    generated_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # A file yields many chunks; deleting the file removes its chunks too.
    chunks: Mapped[list["DocumentChunk"]] = relationship(  # noqa: F821
        back_populates="source_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def has_draft(self) -> bool:
        """True when a generated draft is waiting to be published."""

        return bool(self.generated_content and self.generated_content.get("topics"))

    def __repr__(self) -> str:
        return f"<SourceFile id={self.id} filename={self.filename!r} status={self.status!r}>"
