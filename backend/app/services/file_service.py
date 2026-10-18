"""Query and lifecycle operations for uploaded course files."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import DocumentChunk, SourceFile
from app.models.enums import SourceFileStatus
from app.services.extractor import SUPPORTED_EXTENSIONS, extract_pages


class FileNotFound(Exception):
    """Raised when a SourceFile row (or its bytes) cannot be located."""


class UnsupportedFileType(Exception):
    """Raised when an upload extension is not in the allow-list."""


def chunk_count(db: Session, file_id: int) -> int:
    """Number of chunks persisted for a file (cheap COUNT query)."""

    return int(
        db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.file_id == file_id)
        ).scalar_one()
    )


def get_file_or_404(db: Session, file_id: int) -> SourceFile:
    source_file = db.get(SourceFile, file_id)
    if source_file is None:
        raise FileNotFound(f"No source file with id {file_id}.")
    return source_file


def find_by_hash(db: Session, file_hash: str) -> SourceFile | None:
    """Return the existing row for identical bytes, if any."""

    return db.execute(
        select(SourceFile).where(SourceFile.file_hash == file_hash)
    ).scalar_one_or_none()


def list_files(
    db: Session,
    *,
    status: SourceFileStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[SourceFile]]:
    """Return ``(total, files)`` with chunk counts eagerly loaded."""

    base = select(SourceFile)
    count_base = select(func.count()).select_from(SourceFile)

    if status is not None:
        base = base.where(SourceFile.status == status.value)
        count_base = count_base.where(SourceFile.status == status.value)

    total = int(db.execute(count_base).scalar_one())

    files = db.execute(
        base.options(selectinload(SourceFile.chunks))
        .order_by(SourceFile.upload_date.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return total, list(files)


def validate_extension(filename: str) -> str:
    """Return the lower-cased extension, rejecting unsupported types."""

    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Unsupported file type {suffix or '(none)'!r}. "
            f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return suffix


def page_count_for(source_file: SourceFile) -> int:
    """Number of distinct pages the extractor produced for this file."""

    stored = _stored_path(source_file)
    if stored is None:
        return 0
    try:
        return len(extract_pages(stored))
    except Exception:  # pragma: no cover - defensive
        return 0


def delete_file(db: Session, source_file: SourceFile, *, commit: bool = True) -> int:
    """Delete a file row, its chunks and its stored bytes.

    Returns the number of chunks that were removed.
    """

    chunk_count = (
        db.execute(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.file_id == source_file.id)
        ).scalar_one()
    )

    stored = _stored_path(source_file)

    # Delete children explicitly instead of relying purely on the DB-level
    # cascade -- SQLite only honours `ON DELETE CASCADE` when its
    # `foreign_keys` pragma is on, and being explicit keeps this portable.
    db.execute(delete(DocumentChunk).where(DocumentChunk.file_id == source_file.id))

    db.delete(source_file)
    db.flush()

    if stored is not None and stored.is_file():
        stored.unlink(missing_ok=True)

    if commit:
        db.commit()

    return int(chunk_count)


def _stored_path(source_file: SourceFile) -> Path | None:
    """Resolve the on-disk location of a stored upload."""

    upload_dir = get_settings().upload_path

    direct = upload_dir / source_file.filename
    if direct.is_file():
        return direct

    matches = sorted(upload_dir.glob(f"{source_file.file_hash[:16]}-*"))
    return matches[0] if matches else None


def stored_path_or_none(source_file: SourceFile) -> Path | None:
    """Public accessor used by the API layer."""

    return _stored_path(source_file)
