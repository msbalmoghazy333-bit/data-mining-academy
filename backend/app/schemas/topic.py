"""Schemas for the topic catalogue endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopicRead(BaseModel):
    """One syllabus unit plus the size of its assessment material."""

    id: int
    title_en: str
    title_ar: str
    mastery_status: str
    questions: int = Field(description="Questions in the bank for this topic.")
    flashcards: int = Field(description="Flashcards available for this topic.")


class TopicList(BaseModel):
    total: int
    items: list[TopicRead]
