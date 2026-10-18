"""Course file management endpoints.

The router is mounted under ``/api`` (see ``settings.api_v1_prefix``) and
carries its own ``/v1`` segment, so the public paths are:

    POST   /api/v1/files/upload             upload + extract + chunk
    GET    /api/v1/files                    list uploads with statuses
    GET    /api/v1/files/{id}/preview       inspect pages & chunks
    POST   /api/v1/files/{id}/retry         re-run extraction on failures
    DELETE /api/v1/files/{id}               remove file + chunks

``/api/health`` intentionally stays outside ``/v1`` so infrastructure probes
never break when the business API is re-versioned.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import SourceFile
from app.models.enums import SourceFileStatus
from app.schemas.document_chunk import DocumentChunkRead, FilePreview, PagePreview
from app.schemas.source_file import SourceFileList, SourceFileRead
from app.services import file_service, pipeline, storage
from app.services.extractor import extract_pages

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/files", tags=["files"])

DbSession = Annotated[Session, Depends(get_db)]

PREVIEW_CHARS = 300

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=SourceFileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a course file and run the extraction pipeline",
)
async def upload_file(
    db: DbSession,
    file: Annotated[UploadFile, File(description="PDF, DOCX, PPTX, TXT or MD")],
) -> SourceFileRead:
    """Persist an upload, extract its pages, chunk them and store the result."""

    settings = get_settings()

    # --- validate type -----------------------------------------------------
    try:
        file_service.validate_extension(file.filename or "")
    except file_service.UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    # --- reject duplicates before writing anything -------------------------
    # The hash needs the bytes, so we read them once here and hand a fresh
    # in-memory copy to the storage layer.
    payload = await file.read()
    await file.seek(0)

    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

    if len(payload) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit.",
        )

    file_hash = storage.sha256_bytes(payload)

    existing = file_service.find_by_hash(db, file_hash)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This exact file has already been uploaded.",
                "existing_file_id": existing.id,
                "existing_filename": existing.filename,
                "upload_date": existing.upload_date.isoformat(),
            },
        )

    # --- store -------------------------------------------------------------
    try:
        stored = storage.save_bytes(payload, file.filename or "unnamed")
    except storage.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    source_file = SourceFile(
        filename=stored.original_name,
        file_hash=stored.file_hash,
        file_type=stored.file_type,
        file_size=stored.size,
        status=SourceFileStatus.UPLOADED.value,
    )
    db.add(source_file)
    db.flush()

    # --- extract + chunk ---------------------------------------------------
    # Failures are captured on the row (status=failed) rather than raised, so
    # the client still gets the file id back and can POST /retry later.
    pipeline.process_source_file(db, source_file, commit=True)

    return _to_read(db, source_file)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get("", response_model=SourceFileList, summary="List uploaded files")
def list_files(
    db: DbSession,
    status_filter: Annotated[
        SourceFileStatus | None,
        Query(alias="status", description="Filter by pipeline status."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceFileList:
    total, files = file_service.list_files(db, status=status_filter, limit=limit, offset=offset)
    return SourceFileList(total=total, items=[_to_read(db, f) for f in files])


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


@router.get(
    "/{file_id}/preview",
    response_model=FilePreview,
    summary="Inspect extracted text and pages before publishing",
)
def preview_file(file_id: int, db: DbSession) -> FilePreview:
    source_file = file_service.get_file_or_404(db, file_id)

    stored = file_service.stored_path_or_none(source_file)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The stored file is missing from disk; re-upload it.",
        )

    try:
        pages = extract_pages(stored)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Could not re-extract text: {exc}",
        )

    page_previews = [
        PagePreview(
            page_number=page.page_number,
            word_count=page.word_count,
            preview=page.text[:PREVIEW_CHARS],
            full_text=page.text,
        )
        for page in pages
    ]

    chunks = sorted(source_file.chunks, key=lambda c: c.chunk_index)
    chunk_reads = [
        DocumentChunkRead(
            id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_or_slide_number=chunk.page_or_slide_number,
            topic_tag=chunk.topic_tag,
            word_count=len(chunk.content.split()),
        )
        for chunk in chunks
    ]

    return FilePreview(
        file=_to_read(db, source_file),
        pages=page_previews,
        chunks=chunk_reads,
        total_pages=len(pages),
        total_words=sum(p.word_count for p in pages),
        total_chunks=len(chunk_reads),
    )


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


@router.post(
    "/{file_id}/retry",
    response_model=SourceFileRead,
    summary="Re-run extraction for a failed (or any) file",
)
def retry_file(file_id: int, db: DbSession) -> SourceFileRead:
    source_file = file_service.get_file_or_404(db, file_id)

    stored = file_service.stored_path_or_none(source_file)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="The stored file is missing from disk; re-upload it.",
        )

    was_published = source_file.status == SourceFileStatus.PUBLISHED.value
    pipeline.process_source_file(db, source_file, commit=True)

    # Re-extraction replaced the chunks: any vectors still pointing at the
    # old text are stale and must go (the file will re-index on next publish).
    if not was_published or source_file.status != SourceFileStatus.PUBLISHED.value:
        _purge_vectors(source_file.id)

    return _to_read(db, source_file)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a file and its extracted chunks",
)
def delete_file(file_id: int, db: DbSession) -> dict:
    source_file = file_service.get_file_or_404(db, file_id)
    removed_chunks = file_service.delete_file(db, source_file, commit=True)

    # The RAG index must never answer from a deleted file.
    _purge_vectors(source_file.id)

    return {
        "deleted": True,
        "file_id": file_id,
        "filename": source_file.filename,
        "deleted_chunks": removed_chunks,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _purge_vectors(file_id: int) -> int:
    """Best-effort vector cleanup (delete / re-extract).

    Deletion must never fail because of the optional vector index, so any
    problem here is logged and swallowed.
    """

    try:
        from app.services.vector_store import get_vector_store

        return get_vector_store().remove_file(file_id)
    except Exception as exc:  # noqa: BLE001 - optional subsystem
        logger.warning("Vector cleanup skipped for file %s: %s", file_id, exc)
        return 0


def _to_read(db: Session, source_file: SourceFile) -> SourceFileRead:
    """Build a :class:`SourceFileRead`, including derived counts.

    Counts come from explicit queries rather than the ORM relationship, which
    may not be loaded yet right after a pipeline run.
    """

    return SourceFileRead(
        id=source_file.id,
        filename=source_file.filename,
        file_hash=source_file.file_hash,
        file_type=source_file.file_type,
        file_size=source_file.file_size,
        status=SourceFileStatus(source_file.status),
        upload_date=source_file.upload_date,
        error_message=source_file.error_message,
        chunk_count=file_service.chunk_count(db, source_file.id),
        page_count=file_service.page_count_for(source_file),
        has_draft=source_file.has_draft,
    )
