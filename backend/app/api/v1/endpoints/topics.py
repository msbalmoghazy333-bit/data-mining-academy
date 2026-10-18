"""Topic catalogue endpoint.

    GET /api/v1/topics   list syllabus topics with bank sizes

The quiz screen uses this to offer a topic filter; the lesson viewer and the
revision centre will reuse it as their table of contents.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.topic import TopicList
from app.services import topic_service

router = APIRouter(prefix="/v1/topics", tags=["topics"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=TopicList, summary="List syllabus topics with bank sizes")
def list_topics(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TopicList:
    """Read-only catalogue — no LLM, no side effects."""

    total, items = topic_service.list_topics(db, limit=limit, offset=offset)
    return TopicList(total=total, items=items)
