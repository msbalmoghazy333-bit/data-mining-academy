"""Draft & publish endpoints for AI-generated course content.

    POST /api/v1/files/{file_id}/generate   chunks --LLM--> draft on the row
    POST /api/v1/files/{file_id}/publish    draft --rows--> topics/lessons/...
    GET  /api/v1/files/{file_id}/draft      inspect the staged draft

``generate`` never writes to the syllabus tables; ``publish`` is strictly
additive and idempotent, so re-running it cannot destroy learner progress or
previously published material.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SourceFile
from app.models.enums import SourceFileStatus
from app.schemas.generated import (
    DetectedTopic,
    DraftPreview,
    DraftTopicSummary,
    GenerateResponse,
    PublishResponse,
)
from app.services import content_generator
from app.services.content_generator import (
    GenerationError,
    NoChunksError,
    NoDraftError,
    generate_content,
    publish_content,
)
from app.services.file_service import get_file_or_404
from app.services.llm_service import LLMError, LLMNotConfigured, LLMUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/files", tags=["generation"])

DbSession = Annotated[Session, Depends(get_db)]

# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------


@router.post(
    "/{file_id}/generate",
    response_model=GenerateResponse,
    summary="Generate educational content from a file's chunks (staged as a draft)",
)
def generate_file_content(file_id: int, db: DbSession) -> GenerateResponse:
    """Run topic detection + per-topic content generation.

    The result is stored on ``SourceFile.generated_content`` only. Nothing is
    published to learners until ``POST /{file_id}/publish`` is called.
    """

    source_file = _require_ready_file(db, file_id)

    try:
        summary = generate_content(db, source_file)
    except LLMNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LLMUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except NoChunksError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except GenerationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))

    return GenerateResponse(
        source_file_id=summary.source_file_id,
        filename=summary.filename,
        topic_count=summary.topic_count,
        new_topics=summary.new_topics,
        existing_topics=summary.existing_topics,
        model=summary.model,
        prompt_tokens=summary.prompt_tokens,
        completion_tokens=summary.completion_tokens,
        topics=[
            DetectedTopic(
                title_en=topic.title_en,
                title_ar=topic.title_ar,
                is_new=topic.is_new,
                chunk_indexes=topic.chunk_indexes,
            )
            for topic in summary.topics
        ],
        message=(
            f"Staged {summary.topic_count} topic(s) as a draft. "
            "Nothing was published yet — review it, then POST /publish."
        ),
    )


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


@router.post(
    "/{file_id}/publish",
    response_model=PublishResponse,
    summary="Publish a staged draft additively",
)
def publish_file_content(file_id: int, db: DbSession) -> PublishResponse:
    """Materialise the draft into the syllabus and mark the file published."""

    source_file = get_file_or_404(db, file_id)

    try:
        summary = publish_content(db, source_file)
    except NoDraftError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    vectors_indexed, index_ok = _index_file_vectors(db, source_file)

    return PublishResponse(
        source_file_id=summary.source_file_id,
        filename=summary.filename,
        status=SourceFileStatus.PUBLISHED.value,
        topics_created=summary.topics_created,
        topics_matched=summary.topics_matched,
        lessons_created=summary.lessons_created,
        lessons_updated=summary.lessons_updated,
        questions_created=summary.questions_created,
        questions_skipped=summary.questions_skipped,
        flashcards_created=summary.flashcards_created,
        flashcards_skipped=summary.flashcards_skipped,
        vectors_indexed=vectors_indexed if index_ok else None,
        message=(
            f"{summary.message}"
            + (" Vector index updated — the AI tutor can answer from it now." if index_ok else "")
        ),
    )


# ---------------------------------------------------------------------------
# Draft preview
# ---------------------------------------------------------------------------


@router.get(
    "/{file_id}/draft",
    response_model=DraftPreview,
    summary="Inspect the staged draft without publishing it",
)
def get_file_draft(file_id: int, db: DbSession) -> DraftPreview:
    source_file = get_file_or_404(db, file_id)
    draft = source_file.generated_content or {}
    topics = draft.get("topics") or []

    summaries = []
    for topic in topics:
        lesson = topic.get("lesson") or {}
        summaries.append(
            DraftTopicSummary(
                title_en=topic.get("title_en", ""),
                title_ar=topic.get("title_ar", ""),
                question_count=len(topic.get("questions") or []),
                flashcard_count=len(topic.get("flashcards") or []),
                lesson_chars=len(lesson.get("content_ar") or ""),
                objectives=list(lesson.get("objectives") or []),
                summary=lesson.get("summary") or "",
            )
        )

    return DraftPreview(
        source_file_id=source_file.id,
        filename=source_file.filename,
        has_draft=source_file.has_draft,
        model=draft.get("model", ""),
        generated_at=draft.get("generated_at", ""),
        topic_count=len(topics),
        topics=summaries,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index_file_vectors(db: Session, source_file: SourceFile) -> tuple[int, bool]:
    """Index a published file's chunks for the RAG tutor.

    Best effort: publishing must succeed even when the embedding backend is
    unavailable (no API key, offline Chrome/ONNX download, ...), so failures
    are logged and reported through ``vectors_indexed=null`` instead of
    failing the request. The next ``ensure_published_indexed`` sweep (app
    startup) picks the file up again.
    """

    try:
        from app.services.vector_store import get_vector_store

        return get_vector_store().index_file(source_file, db=db), True
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, log loudly
        logger.warning(
            "Vector indexing skipped for file %s: %s", source_file.id, exc
        )
        return 0, False


def _require_ready_file(db: Session, file_id: int) -> SourceFile:
    """Generation needs extracted chunks, so the file must have passed Step 1."""

    source_file = get_file_or_404(db, file_id)

    if source_file.status == SourceFileStatus.FAILED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"File '{source_file.filename}' failed extraction "
                f"({source_file.error_message}). POST /retry first."
            ),
        )

    if not source_file.chunks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This file has no extracted chunks yet.",
        )

    return source_file
