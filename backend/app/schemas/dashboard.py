"""Schemas for the learner dashboard summary."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class FileStats(BaseModel):
    total: int
    by_status: dict[str, int] = {}


class TopicStats(BaseModel):
    total: int
    studied: int = Field(description="Topics whose mastery is beyond not_started.")
    mastery: dict[str, int] = {}


class RecentAttempt(BaseModel):
    attempt_id: int
    topic_id: int
    topic_title_en: str = ""
    topic_title_ar: str = ""
    score: int = Field(ge=0, le=100)
    total_questions: int
    completed_at: datetime


class RecommendedTopic(BaseModel):
    topic_id: int
    title_en: str
    title_ar: str
    mastery_status: str
    attempts: int = Field(description="Total attempts recorded for the topic.")
    last_score: int | None = None


class DashboardSummary(BaseModel):
    files: FileStats
    topics: TopicStats
    recent_attempts: list[RecentAttempt] = []
    recommended: list[RecommendedTopic] = []
