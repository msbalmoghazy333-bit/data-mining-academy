"""DocumentChunk model — a vectorizable slice of an uploaded file."""

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "chunk_index", name="uq_document_chunks_file_id_chunk_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    file_id: Mapped[int] = mapped_column(
        ForeignKey("source_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 1-based page number for PDFs / slide number for PPTX.
    page_or_slide_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_tag: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # ChromaDB stores the embedding; we keep the generated id in sync
    # so a chunk can be re-embedded or deleted deterministically.
    chroma_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    source_file: Mapped["SourceFile"] = relationship(back_populates="chunks")  # noqa: F821

    def __repr__(self) -> str:
        return f"<DocumentChunk id={self.id} file_id={self.file_id} index={self.chunk_index}>"
