"""Dashboard analytics endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.dashboard import (
    DashboardSummary,
    FileStats,
    RecentAttempt,
    RecommendedTopic,
    TopicStats,
)
from app.services import dashboard_service

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])

DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Learner overview: files, mastery, recent attempts, revision queue",
)
def dashboard_summary(db: DbSession) -> DashboardSummary:
    """Read-only roll-up across files, topics, attempts and mastery."""

    data = dashboard_service.build_summary(db)

    return DashboardSummary(
        files=FileStats.model_validate(data["files"]),
        topics=TopicStats.model_validate(data["topics"]),
        recent_attempts=[
            RecentAttempt.model_validate(attempt) for attempt in data["recent_attempts"]
        ],
        recommended=[RecommendedTopic.model_validate(entry) for entry in data["recommended"]],
    )
