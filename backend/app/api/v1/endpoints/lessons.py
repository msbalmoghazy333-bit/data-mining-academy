"""Lesson viewer endpoints.

    GET /api/v1/lessons          compact summaries (optional ``?topic_id=``)
    GET /api/v1/lessons/{id}     the full lesson, Markdown body included

Read-only: nothing here touches the LLM or writes to the database.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.lesson import LessonList, LessonRead, LessonSummary
from app.services import lesson_service
from app.services.lesson_service import LessonNotFound

router = APIRouter(prefix="/v1/lessons", tags=["lessons"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=LessonList,
    summary="List published lessons (optionally filtered by topic)",
)
def list_lessons(
    db: DbSession,
    topic_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LessonList:
    """Lightweight catalogue — no Markdown bodies, no side effects."""

    total, items = lesson_service.list_lessons(
        db, topic_id=topic_id, limit=limit, offset=offset
    )

    return LessonList(
        total=total,
        items=[LessonSummary.model_validate(item) for item in items],
    )


@router.get(
    "/{lesson_id}",
    response_model=LessonRead,
    summary="Full published lesson (Markdown body + structured blocks)",
)
def get_lesson(lesson_id: int, db: DbSession) -> LessonRead:
    """The reading view's single fetch per lesson."""

    try:
        data = lesson_service.get_lesson(db, lesson_id)
    except LessonNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return LessonRead.model_validate(data)
