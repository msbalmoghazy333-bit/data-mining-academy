"""Extraction pipeline: SourceFile -> pages -> chunks -> database.

State machine::

    uploaded ──► processing ──► ready_for_review
                   │
                   └──────────► failed  (error_message populated; retryable)

The pipeline is deliberately synchronous so it is trivially testable. To make
uploads feel instant later, call :func:`process_source_file` from a
``BackgroundTasks`` worker without changing anything below.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import DocumentChunk, SourceFile
from app.models.enums import SourceFileStatus
from app.services.chunker import chunk_pages
from app.services.extractor import ExtractionError, ExtractedPage, extract_pages
from app.services.storage import sha256_file

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when extraction/chunking fails for a file."""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Summary of one pipeline run."""

    source_file: SourceFile
    pages: list[ExtractedPage]
    chunk_count: int

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def total_words(self) -> int:
        return sum(page.word_count for page in self.pages)


def process_source_file(
    db: Session,
    source_file: SourceFile,
    *,
    commit: bool = True,
) -> PipelineResult:
    """Run extraction + chunking for ``source_file`` and persist the result.

    Any failure flips the row to ``failed`` with a human-readable
    ``error_message`` instead of propagating, so one bad file never poisons a
    batch upload.
    """

    storage_path = _resolve_storage_path(source_file)

    source_file.status = SourceFileStatus.PROCESSING.value
    source_file.error_message = None
    db.flush()

    pages: list[ExtractedPage] = []

    try:
        pages = extract_pages(storage_path)
        if not pages:
            raise ExtractionError(
                "No extractable text found. The file may be a scanned "
                "image PDF without an OCR layer."
            )

        settings = get_settings()
        chunks = chunk_pages(
            pages,
            target_words=settings.chunk_target_words,
            max_words=settings.chunk_max_words,
            merge_short_pages=settings.chunk_merge_short_pages,
            max_page_span=settings.chunk_max_page_span,
        )

        # Re-running must not duplicate rows: clear whatever a previous
        # attempt produced before inserting fresh chunks.
        db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == source_file.id))

        for chunk in chunks:
            db.add(
                DocumentChunk(
                    file_id=source_file.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_or_slide_number=chunk.page_or_slide_number,
                )
            )

        source_file.status = SourceFileStatus.READY_FOR_REVIEW.value
        source_file.error_message = None

    except ExtractionError as exc:
        logger.warning("Extraction failed for %s: %s", source_file.filename, exc)
        _mark_failed(db, source_file, str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected pipeline failure for %s", source_file.filename)
        _mark_failed(db, source_file, f"Unexpected error: {exc}")

    if commit:
        db.commit()
        db.refresh(source_file)
    else:
        db.flush()

    return PipelineResult(
        source_file=source_file,
        pages=pages if source_file.status == SourceFileStatus.READY_FOR_REVIEW.value else [],
        chunk_count=count_chunks(db, source_file.id),
    )


def _mark_failed(db: Session, source_file: SourceFile, message: str) -> None:
    source_file.status = SourceFileStatus.FAILED.value
    source_file.error_message = message[:2000]
    db.flush()


def _resolve_storage_path(source_file: SourceFile) -> Path:
    """Locate the on-disk file, falling back to a hash-named lookup."""

    from app.core.config import get_settings

    upload_dir = get_settings().upload_path
    candidate = upload_dir / source_file.filename

    if candidate.is_file():
        return candidate

    # The stored name is "<hash[:16]>-<name>", so it is recoverable.
    matches = sorted(upload_dir.glob(f"{source_file.file_hash[:16]}-*"))
    if matches:
        return matches[0]

    raise PipelineError(
        f"Stored file for '{source_file.filename}' is missing from {upload_dir}."
    )


def count_chunks(db: Session, file_id: int) -> int:
    """Number of chunks persisted for a file."""

    return int(
        db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.file_id == file_id)
        ).scalar_one()
    )
